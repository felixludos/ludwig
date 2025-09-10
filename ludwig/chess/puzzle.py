from ..imports import *
from ..base import TaskBase
from ..util import repo_root
from ..util.prompts import SimpleFormalizer

from .helpers import *

import io
import chess
import chess.pgn

# https://github.com/kagisearch/llm-chess-puzzles/tree/main


class Chess_Formalizer(SimpleFormalizer):
	def schema(self) -> JSONOBJ:
		raise NotImplementedError

	@staticmethod
	def default_formalize(fen):
		raise NotImplementedError

	def formalization_args(self, context: JSONOBJ) -> JSONOBJ:
		return {'fen': context['fen']}



@fig.component('chess/puzzle')
class ChessPuzzle(TaskBase):
	_problem_path = repo_root().joinpath('assets', 'chess', 'puzzles_with_pgn.csv')
	_analysis_path = repo_root().joinpath('assets', 'chess', 'analysis.json')
	def __init__(self, *, obs_rep: str = 'fen', hint: Optional[int] = None, **kwargs):
		assert obs_rep in ['fen', 'pgn', 'white', 'active', 'unicode', 'minimal', 'border'], \
			f'Invalid observation representation: {obs_rep}'
		assert isinstance(hint, int) or hint in [None, 'all'], f'Invalid options: {hint!r}'
		super().__init__(**kwargs)
		self._obs_rep = obs_rep
		self._options = hint
		self.data = None
		self.dev_data = None
		self.analysis = None

	@property
	def name(self) -> str:
		return "ChessPuzzle"

	_dev_set_cut = 100
	def prepare(self, seed: Optional[int] = None) -> Any:
		super().prepare(seed)
		if not self._problem_path.exists():
			raise FileNotFoundError(f"Problem data file not found: {self._problem_path}")
		import pandas as pd
		full_data = pd.read_csv(self._problem_path, header=0)
		full_data['GameID'] = full_data['GameUrl'].apply(
			lambda x: x.split('/')[-2] if 'black#' in x else x.split('/')[-1].split('#')[0])
		# split into dev and train sets
		self.data = full_data.iloc[self._dev_set_cut:].reset_index(drop=True)
		self.dev_data = full_data.iloc[:self._dev_set_cut].reset_index(drop=True)
		self.analysis = json.loads(self._analysis_path.read_text())

	def show_keys(self) -> Iterator[str]:
		yield 'question'
		yield 'system'
		yield 'task'
		yield 'legal' # enables judge.interpret() calls in the strategy

	def store_keys(self) -> Iterator[str]:
		yield 'fen'
		yield 'question'
		yield 'answer'
		yield 'puzzle_id'
		yield 'num_legal_moves'

	def json(self) -> JSONOBJ:
		return {
			'obs_rep': self._obs_rep,
			'hint': self._options,
		}

	@property
	def total_questions(self) -> Optional[int]:
		if self.data is None:
			return None
		return len(self.data)

	@property
	def total_dev_questions(self) -> Optional[int]:
		if self.dev_data is None:
			return None
		return len(self.dev_data)

	def specification(self) -> JSONOBJ:
		return {'answer': 'option', 'options': 'legal'}

	def context(self) -> str:
		return self._system_context

	def description(self) -> str:
		return self._task_description

	def ask_dev(self, index: int) -> JSONOBJ:
		"""Ask a question from the development set."""
		ctx = self.ask(index, dev=True)
		ctx['answer'] = ctx['answer'][0]
		return ctx

	_system_context = "Implement all the rules of chess to solve some chess problems."
	_task_description = ("Can you solve this chess puzzle? You will be given a board position and you must "
						 "find the best move for the side to move. ")
	def ask(self, index: int, dev: bool = False) -> JSONOBJ:
		ctx = {}

		# dict of data
		raw = (self.dev_data if dev else self.data).iloc[index].to_dict()
		ctx['puzzle_id'] = raw['PuzzleId']
		analysis = self.analysis[raw['PuzzleId']]
		board = chess.Board(raw['FEN'])

		game = chess.pgn.read_game(io.StringIO(raw['PGN']))
		moves = raw['Moves'].split()

		assert len(moves) >= 2, f'Not enough moves in puzzle {index}: {moves!r}'
		first_move, answer, *other = moves
		board = game.end().board()
		move = board.push_san(first_move)
		game.end().add_main_variation(move)
		game.headers.clear()

		fen = board.fen()

		active_player = 'white' if board.turn == chess.WHITE else 'black'
		opponent = 'black' if active_player == 'white' else 'white'

		template = '{board}\n\n(where uppercase letters are white pieces and lowercase letters are black pieces)'
		if self._obs_rep == 'pgn':
			obs = f'PGN: {game}'
		elif self._obs_rep == 'fen':
			obs = f"FEN: {fen}"
		elif self._obs_rep == 'white':
			obs = template.format(board=analysis['white_view'])
		elif self._obs_rep == 'active':
			obs = template.format(board=analysis[f'{active_player}_view'])
		elif self._obs_rep == 'unicode':
			obs = board.unicode(invert_color=True)
		else:
			obs = template.format(board=self._render_board(board))

		question = (f"{opponent.capitalize()} just played {moves[0]}. "
					f"Given the resulting board position:\n\n{obs}\n\nWhat is the best move for {active_player}? "
						   f"Answer using the UCI or SAN format.")

		ctx['fen'] = fen
		ctx['player'] = active_player

		ctx['legal'] = [board.san(move) for move in board.legal_moves] + [move.uci() for move in board.legal_moves]
		ctx['num_legal_moves'] = len(ctx['legal']) // 2
		hint = None
		if self._options is None:
			pass
		elif self._options == 'all':
			# return all legal moves as options in san format
			options = sorted(move.uci() for move in board.legal_moves)
			ctx['options'] = options
			options = ', '.join(sorted(options))
			hint = f'Possible moves are (the correct answer is one of these): {options}'
		else:
			assert self._options > 0, f'Invalid number of options: {self._options!r}'

			top = [move['Move'] for move in analysis['moves'][:self._options]]
			ctx['options'] = top
			top = sorted(top)
			options = ', '.join(top)
			hint = f'Some moves to consider are: {options}'

		if hint is not None:
			question = f'{question}\n{hint}'

		ctx['question'] = question

		ctx['rationale'] = list(self._rationale(board, raw['Themes'].split(), answer,
												[move['Move'] for move in analysis['moves'][:4]]))

		ctx['answer'] = [answer, board.san(board.parse_uci(answer))]

		ctx['system'] = self._system_context
		ctx['task'] = self._task_description
		return ctx

	def _render_board(self, board: chess.Board) -> str:
		if self._obs_rep == 'minimal':
			return str(board)
		elif self._obs_rep == 'unicode':
			return board.unicode(invert_color=True)
		elif self._obs_rep == 'border':
			return board_to_text(board)
		else:
			raise ValueError(f'Unsupported observation representation: {self._obs_rep!r}')

	def _rationale(self, board: chess.Board, tags: List[str], answer: str, top_moves: List[str]) -> Iterator[str]:
		# https://gemini.google.com/app/65c85f24a87f2712
		tag_set = set(tags)

		# Expanded tag definitions based on the new list
		PHASE_TAGS = {
			'opening': "the **opening**", 'middlegame': "the **middlegame**",
			'endgame': "the **endgame**", 'rookEndgame': "a **rook endgame**",
			'knightEndgame': "a **knight endgame**", 'bishopEndgame': "a **bishop endgame**",
			'queenEndgame': "a **queen endgame**", 'pawnEndgame': "a **pawn endgame**",
			'queenRookEndgame': "a **queen and rook endgame**"
		}
		TACTIC_TAGS = {
			'pin': 'pin', 'fork': 'fork', 'skewer': 'skewer', 'sacrifice': 'sacrifice',
			'discoveredAttack': 'discovered attack', 'doubleCheck': 'double check',
			'attraction': 'attraction', 'deflection': 'deflection', 'interference': 'interference',
			'clearance': 'clearance', 'xRayAttack': 'x-ray attack',
			'hangingPiece': 'hanging piece', 'trappedPiece': 'trapped piece',
			'capturingDefender': 'capturing a defender', 'exposedKing': 'exposed king',
			'advancedPawn': 'advanced pawn', 'promotion': 'promotion', 'underPromotion': 'underpromotion',
			'enPassant': 'en passant', 'zugzwang': 'zugzwang', 'intermezzo': 'intermezzo',
			'quietMove': 'quiet move', 'attackingF2F7': 'attack on f2/f7',
			'kingsideAttack': 'kingside attack', 'queensideAttack': 'queenside attack',
			'backRankMate': 'back-rank mate', 'anastasiaMate': "anastasia's mate",
			'arabianMate': "arabian mate", 'dovetailMate': "dovetail mate",
			'hookMate': "hook mate", 'doubleBishopMate': 'double bishop mate'
		}

		### Step 1: Assess Phase and Goal
		# Prioritize specific endgame tags over general ones
		phase = next((desc for tag, desc in PHASE_TAGS.items() if tag in tag_set and 'Endgame' in tag), None)
		if not phase:
			phase = next((desc for tag, desc in PHASE_TAGS.items() if tag in tag_set), "the position")

		goal = "find the best move"
		if 'mate' in tag_set:
			mate_in = next((t.replace('mateIn', ' in ') for t in tag_set if t.startswith('mateIn')), "")
			goal = f"deliver **checkmate**{mate_in}"
		elif 'crushing' in tag_set:
			goal = "achieve a **crushing** advantage"
		elif 'advantage' in tag_set:
			goal = "gain a decisive **advantage**"
		elif 'defensiveMove' in tag_set:
			goal = "find the crucial **defensive move**"

		yield f"First, I'll assess {phase}. The main objective is to {goal}."

		### Step 2: Identify Key Tactics
		found_tactics = [desc for tag, desc in TACTIC_TAGS.items() if tag in tag_set]
		if found_tactics:
			if len(found_tactics) > 1:
				tactics_str = ", ".join(f"**{t}**" for t in found_tactics[:-1]) + f" and **{found_tactics[-1]}**"
				yield f"The key tactical motifs to consider are {tactics_str}."
			else:
				yield f"The key tactical motif appears to be a **{found_tactics[0]}**."
		else:
			yield "I will scan for general tactical weaknesses and forcing moves."

		### Step 3: Formulate a Plan
		plan = "I will search for candidate moves based on these ideas."
		if 'defensiveMove' in tag_set:
			plan = "My plan is to identify the opponent's primary threat and find the precise move to neutralize it."
		elif 'zugzwang' in tag_set:
			plan = "The plan is likely to involve a subtle **quiet move** to pass the turn, putting the opponent in **zugzwang**."
		elif 'quietMove' in tag_set:
			plan = "I'll look for a surprising **quiet move** that sets up an unstoppable threat."
		elif 'capturingDefender' in tag_set:
			plan = "I will formulate a plan to execute a **capturing defender** tactic, removing a key defensive piece."
		elif found_tactics:
			plan = f"My search will focus on moves that create opportunities for a {', a '.join(f'**{t}**' for t in found_tactics)}."
		yield plan

		### Step 4: Verify the Solution
		verification = "Finally, I must calculate the sequence to ensure it is winning."
		if 'defensiveMove' in tag_set:
			verification = "I will verify that this move successfully parries all threats and secures the position."
		elif mate_in := next((t for t in tag_set if t.startswith('mateIn')), None):
			verification = f"I must verify the chosen move forces **{mate_in.replace('mateIn', 'mate in ')}** against all defenses."
		elif 'advantage' in tag_set or 'crushing' in tag_set:
			verification = f"I will confirm the move leads to the stated **advantage**."

		length_desc = ""
		if 'oneMove' in tag_set:
			length_desc = "The solution is a single, decisive move."
		elif 'short' in tag_set:
			length_desc = "The sequence should be **short** and forceful."
		elif 'long' in tag_set:
			length_desc = "The sequence is **long**, requiring deep calculation."
		elif 'veryLong' in tag_set:
			length_desc = "The sequence is **very long**, demanding precise, extended calculation."

		yield f"{verification} {length_desc}".strip()

		moves = ', '.join(sorted(top_moves))
		yield f'Based on this analysis, some candidate best moves are {moves}.'

		yield f'Upon further thought, the best next move appears to be **{answer}**.'



def test_chess_task():

	task = ChessPuzzle(obs_rep='fen', hint=3)
	task.prepare()

	ctx = task.ask(0)
	print()
	print(ctx)








