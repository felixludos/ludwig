import chess

from ..imports import *
from ..base import TaskBase
from ..util import ToolBase, ToolError, repo_root
import re
from .helpers import *


@fig.component('chess/tool/next-move')
class NextMove(ToolBase):
	@property
	def name(self) -> str:
		return 'next_moves'

	def description(self) -> str:
		return ('Get all legal next moves for the given chess game in FEN format. '
				'Returns an empty list if the game is over.')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"fen": {
							"type": "string",
							"description": "The current state of the chess game in FEN format. "
										   "Must be a valid FEN string and include all necessary information. ",
						},
					},
					"required": ["fen"]
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'

		fen = arguments.get('fen', None)
		if fen is None or not isinstance(fen, str):
			raise ToolError('FEN string is required')

		try:
			board = chess.Board(fen)
		except ValueError as e:
			raise ToolError(f'Invalid FEN string: {fen!r}. Error: {e}')
		if not board.is_valid():
			raise ToolError(f'Invalid FEN string: {fen}')

		if board.is_game_over():
			return '[]'

		moves = [move.uci() for move in board.legal_moves]
		return json.dumps(moves)


@fig.component('chess/tool/draw-board')
class DrawBoard(ToolBase):
	@property
	def name(self) -> str:
		return 'draw_board'

	def description(self) -> str:
		return ('Draw the chess board in ASCII format for the given FEN string. '
				'Returns an empty string if the game is over.')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"fen": {
							"type": "string",
							"description": "The current state of the chess game in FEN format. "
										   "Must be a valid FEN string and include all necessary information. ",
						},
					},
					"required": ["fen"]
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'

		fen = arguments.get('fen', None)
		if fen is None or not isinstance(fen, str):
			raise ToolError('FEN string is required')

		try:
			board = chess.Board(fen)
		except ValueError as e:
			raise ToolError(f'Invalid FEN string: {fen!r}. Error: {e}')
		if not board.is_valid():
			raise ToolError(f'Invalid FEN string: {fen}')

		if board.is_game_over():
			return ''

		return board_to_text(board)



class StockfishTool(ToolBase):
	def __init__(self, stockfish_path: Union[str, Path], **kwargs):
		stockfish_path = Path(stockfish_path)
		super().__init__(**kwargs)
		if not stockfish_path.exists():
			raise FileNotFoundError(f'Stockfish binary not found at {stockfish_path}')
		self._stockfish_path = stockfish_path
		import stockfish
		self.stockfish = stockfish.Stockfish(str(self._stockfish_path))
		self._stockfish_error = stockfish.StockfishException


@fig.component('chess/tool/stockfish/best-move')
class StockfishBestNextMove(StockfishTool):
	@property
	def name(self) -> str:
		return 'best_move'

	def description(self) -> str:
		return ('Get the best next move for the given chess game in FEN format using Stockfish. '
				'Returns an empty string if the game is over.')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"fen": {
							"type": "string",
							"description": "The current state of the chess game in FEN format. "
										   "Must be a valid FEN string and include all necessary information. ",
						},
					},
					"required": ["fen"]
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'

		fen = arguments.get('fen', None)
		if fen is None or not isinstance(fen, str):
			raise ToolError('FEN string is required')

		try:
			board = chess.Board(fen)
		except ValueError as e:
			raise ToolError(f'Invalid FEN string: {fen!r}. Error: {e}')
		if not board.is_valid():
			raise ToolError(f'Invalid FEN string: {fen}')

		self.stockfish.set_fen_position(fen)

		try:
			best_move = self.stockfish.get_best_move()
		except self._stockfish_error as e:
			raise ToolError(str(e))

		if best_move:
			board = chess.Board(fen)
			move = board.parse_san(best_move)
			return str(move)
		return ''


from ..util.prompts import ToolAdapter


@fig.component('chess/tool/stockfish/adapted-best-move')
class AdaptedStockfishBestNextMove(ToolAdapter, StockfishBestNextMove):
	def decode(self, raw: JSONOBJ) -> JSONOBJ:
		return {'fen': super().decode(raw)}

	def call(self, arguments: JSONDATA, *, seed: Optional[int] = None) -> str:
		try:
			return super().call(arguments, seed=seed)
		except ToolError as e:
			if str(e).startswith('Invalid FEN string'):
				raise ToolError(f'Invalid game state provided.')
			raise e



@fig.component('chess/tool/stockfish/eval-board')
class StockfishEvalBoard(StockfishTool):
	@property
	def name(self) -> str:
		return 'eval_board'

	def description(self) -> str:
		return ('Evaluate the given chess board in FEN format using Stockfish. '
				'Returns the evaluation score (in standard units of pawns) '
				'where positive values indicate an advantage for white, '
				'negative values indicate an advantage for black, and zero indicates a balanced position. ')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"fen": {
							"type": "string",
							"description": "The current state of the chess game in FEN format. "
										   "Must be a valid FEN string and include all necessary information. ",
						},
					},
					"required": ["fen"]
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'

		fen = arguments.get('fen', None)
		if fen is None or not isinstance(fen, str):
			raise ToolError('FEN string is required')

		try:
			board = chess.Board(fen)
		except ValueError as e:
			raise ToolError(f'Invalid FEN string: {fen!r}. Error: {e}')
		if not board.is_valid():
			raise ToolError(f'Invalid FEN string: {fen}')

		self.stockfish.set_fen_position(fen)

		evaluation = self.stockfish.get_evaluation()

		score = evaluation.get('value', None)

		if score is None:
			raise ToolError('Failed to evaluate the board position')

		return str(score/100)  # Convert centipawns to pawns for easier interpretation



@fig.component('chess/tool/stockfish/eval-move')
class StockfishEvalMove(StockfishTool):
	@property
	def name(self) -> str:
		return 'eval_move'

	def description(self) -> str:
		return ('Evaluate the given chess move in the context of the current board position in FEN format using Stockfish. '
				'Returns the evaluation score (in standard units of pawns) '
				'where positive values indicate an advantage for white, '
				'negative values indicate an advantage for black, and zero indicates a balanced position. ')

	def schema(self, style: str = None) -> JSONOBJ:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description(),
				"parameters": {
					"type": "object",
					"properties": {
						"fen": {
							"type": "string",
							"description": "The current state of the chess game in FEN format. "
										   "Must be a valid FEN string and include all necessary information. ",
						},
						"move": {
							"type": "string",
							"description": "The move to evaluate in UCI format (e.g., 'e2e4'). "
										   "Must be a valid move in the context of the given FEN.",
						},
					},
					"required": ["fen", "move"]
				}
			}
		}

	def call(self, arguments: JSONOBJ, *, seed: Optional[int] = None) -> str:
		assert isinstance(arguments, dict), f'Invalid arguments type: {arguments}'

		fen = arguments.get('fen', None)
		move = arguments.get('move', None)

		if fen is None or not isinstance(fen, str):
			raise ToolError('FEN string is required')

		if move is None or not isinstance(move, str):
			raise ToolError('Move in UCI format is required')

		try:
			board = chess.Board(fen)
		except ValueError as e:
			raise ToolError(f'Invalid FEN string: {fen!r}. Error: {e}')

		if not board.is_valid():
			raise ToolError(f'Invalid FEN string: {fen}')

		chess_move = None
		try:
			chess_move = chess.Move.from_uci(move)
		except chess.InvalidMoveError as e:
			try:
				chess_move = board.parse_san(move)
			except chess.AmbiguousMoveError:
				raise ToolError('Ambiguous move provided. Please use UCI format or provide a clear SAN move.')
			except chess.IllegalMoveError:
				raise ToolError(f'Illegal move provided: {move!r}. Please provide a valid UCI or SAN move.')
			except chess.InvalidMoveError:
				raise ToolError(f'Invalid move provided: {move!r}. Please provide a valid UCI or SAN move.')
			if chess_move is None:
				raise ToolError(f'Invalid move provided: {move!r}. Please provide a valid UCI or SAN move.')

		if chess_move not in board.legal_moves:
			raise ToolError(f'Move {move!r} is not legal for the given board position')

		board.push(chess_move)
		self.stockfish.set_fen_position(board.fen())

		evaluation = self.stockfish.get_evaluation()
		score = evaluation.get('value', None)
		if score is None:
			raise ToolError('Failed to evaluate the move')
		return str(score / 100)  # Convert centipawns to pawns for easier interpretation



def test_chess_tools():

	stockfish_path = r'C:\Users\anwan\Downloads\stockfish-windows-x86-64\stockfish\stockfish-windows-x86-64.exe'

	tool = StockfishEvalBoard(stockfish_path)

	fen = '4kbnr/3b1ppp/p7/qp1pPB2/5BQ1/8/1P3PPP/2R3K1 b k - 1 18' # should be about -3.9

	out = tool.call({'fen': fen})
	assert isinstance(out, str), f'Expected string output, got {type(out)}'
	print()
	print(f'Evaluation for FEN "{fen}": {out}')

	assert float(out) < -2, f'Expected evaluation to be less than -2, got {out}'



