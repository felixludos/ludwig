from .imports import *
from ..abstract import AbstractStrategy, AbstractJudge, AbstractTask, JSONDATA, JSONOBJ
from ..errors import StrategyFailure


class AbstractGame(AbstractTask):
	def load_from_request(self, data: JSONDATA) -> JSONDATA:
		"""
		Load game state from a request.
		"""
		raise NotImplementedError("This method should be implemented in subclasses.")

	def generate_move(self, data: JSONDATA, strategy: AbstractStrategy = None) -> JSONDATA:
		"""
		Take a step in the game using the provided strategy.
		"""
		raise NotImplementedError("This method should be implemented in subclasses.")

	def send_reply(self, data: JSONOBJ, gen: JSONOBJ, log: List[JSONOBJ]) -> JSONOBJ:
		raise NotImplementedError("This method should be implemented in subclasses.")


class GameBase(AbstractGame, fig.Configurable):
	def __init__(self, judge: Optional[AbstractJudge] = None, **kwargs):
		super().__init__(**kwargs)
		self.judge = judge

	def load_from_request(self, data: JSONOBJ) -> JSONDATA:
		return data

	def random_move(self, data: JSONDATA):
		raise NotImplementedError

	def generate_move(self, data: JSONDATA, strategy: AbstractStrategy = None) -> JSONDATA:
		"""
		Take a step in the game using the provided strategy.
		"""
		stats_log = {}
		proc = {}

		problem = self.load_from_request(data)

		info = self.task.side_information(problem)
		if info is not None:
			proc.update(info)
		if self._include_gt_info:
			proc['problem'] = problem

		question = self.observe(problem)

		failed = False
		with strategy.collect_stats() as stats:
			try:
				response, steps = strategy.solve(question, side_information=info)
			except StrategyFailure as e:
				response = str(e) if type(e) == StrategyFailure else f'{e.__class__.__name__}: {e}'
				steps = {'error': type(e).__name__, 'error_message': str(e), 'traceback': traceback.format_exc()}
				failed = True
		if len(stats):
			stats_log.update(stats)
		if steps is not None:
			proc.update(steps)

		if failed:
			decision = None
		elif self.judge is None and not self.is_judge:
			decision = response
		else:
			if self.judge is None:
				verdict, decision, judgement = self.evaluate(response, problem, None)
			else:
				with self.judge.collect_stats() as judge_stats:
					decision, judgement = self.judge.interpret(question, response)
				if len(judge_stats):
					stats_log['judge'] = judge_stats
			if judgement is not None:
				proc.update(judgement)

		proc['decision'] = decision
		proc['stats'] = stats_log
		return proc

	def send_reply(self, data: JSONOBJ, gen: JSONOBJ, log: List[JSONOBJ]) -> JSONOBJ:
		raise NotImplementedError("This method should be implemented in subclasses.")


@fig.component('chess')
class ChessGame(GameBase):
	pass


@fig.component('tictactoe')
class TicTacToeGame(GameBase):
	pass


@fig.script('bridge', description='Launch demo backend flask server to bridge the LLMs.')
def launch_bridge(cfg: fig.Configuration):
	"""
	Launch the demo backend flask server to bridge the LLMs.
	"""
	games = cfg.pull('games', {})
	for game in games.values():
		game.prepare()

	clients = cfg.pull('clients', {})
	if not len(clients):
		raise ValueError("No clients configured. Please provide at least one client configuration.")
	for c in clients.values():
		c.prepare()

	strats = cfg.pulls('strategies', 'strats', default={})
	if not len(strats):
		raise ValueError("No strategies configured. Please provide at least one strategy configuration.")
	for s in strats.values():
		s.prepare()

	from flask import Flask, request, jsonify
	from flask_cors import CORS
	import chess  # python-chess library
	import random
	import subprocess
	import json  # For parsing output from llm_chess_script_stub

	app = Flask(__name__)
	CORS(app)

	# --- Configuration ---
	USE_BACKEND_STUB = True
	LLM_SCRIPT_PATH = './llm_chess_script_stub.py'  # Make sure this script is executable

	# --- Stubbed LLM Options (Replace with dynamic checking if possible) ---
	available_clients = [{'id': key, 'name': c.ident} for key, c in clients.items()]
	available_strategies = [{'id': key, 'name': s.ident} for key, s in strats.items()]

	@app.route('/get-llm-settings-options', methods=['GET'])
	def get_llm_settings_options_route():
		# In a real scenario, you might check online LLMs or config files.
		return jsonify({
			"models": available_clients,
			"prompting_methods": available_strategies
		})

	@app.route('/get-llm-move', methods=['POST'])
	def get_llm_move_route():
		conversation_log = []
		try:
			data = request.json
			gamename = data.get('game')
			# fen = data.get('fen')
			selected_model_id = data.get('selected_model_id', available_clients[0]['id'])
			selected_prompt_id = data.get('selected_prompting_method_id', available_strategies[0]['id'])

			strategy = strats.get(selected_prompt_id, None)
			client = clients.get(selected_model_id, None)
			if strategy is None:
				strategy.client = client

			game = games.get(gamename)

			res = game.m

			if game == 'chess':
				out = take_chess_step(data, strategy, judge, conversation_log)
			elif game == 'ttt':
				out = take_ttt_step(data, strategy, judge, conversation_log)
			else:
				conversation_log.append({"sender": "Backend", "type": "error", "content": f'invalid game: {game}'})
				return jsonify({'error': f'Error identifying game: {game}', 'details': f'invalid game: {game}',
								'conversationLog': conversation_log}), 500

			conversation_log.append({"sender": "Backend", "type": "request_received",
									 "content": f"Received state: {fen}, Model: {selected_model_id}, Prompt: {selected_prompt_id}"})

			if not fen:
				conversation_log.append({"sender": "Backend", "type": "error", "content": "FEN string missing"})
				return jsonify({'error': 'FEN string missing', 'conversationLog': conversation_log}), 400

			current_board = chess.Board(fen)
			if current_board.is_game_over():
				conversation_log.append({"sender": "Backend", "type": "info", "content": "Game is already over."})
				return jsonify(
					{'error': 'Game is already over according to FEN.', 'conversationLog': conversation_log}), 400

			llm_move_san = None

			if USE_BACKEND_STUB or selected_model_id == "random_mover_stub":
				conversation_log.append({"sender": "Backend", "type": "info",
										 "content": f"Using Backend STUB logic for model: {selected_model_id}."})
				legal_moves = list(current_board.legal_moves)
				if not legal_moves:
					conversation_log.append(
						{"sender": "Backend", "type": "error", "content": "No legal moves available (stub)."})
					return jsonify(
						{'error': 'No legal moves available (stub).', 'conversationLog': conversation_log}), 500

				move = random.choice(legal_moves)
				llm_move_san = current_board.san(move)
				conversation_log.append(
					{"sender": "Backend Stub", "type": "decision", "content": f"Stub chose move: {llm_move_san}"})

			else:
				conversation_log.append({"sender": "Backend", "type": "info",
										 "content": f"Attempting to call LLM script for model: {selected_model_id}, prompt: {selected_prompt_id}."})
				try:
					process = subprocess.run(
						['python3', LLM_SCRIPT_PATH, fen, selected_model_id, selected_prompt_id],
						capture_output=True, text=True, check=True, timeout=30
					)
					script_output_raw = process.stdout.strip()
					conversation_log.append(
						{"sender": "LLM Script Host", "type": "raw_script_output", "content": script_output_raw})

					if not script_output_raw:
						raise ValueError("LLM script returned empty output.")

					try:
						script_output_json = json.loads(script_output_raw)
						llm_move_san = script_output_json.get("move")
						script_conversation_log = script_output_json.get("conversationLog", [])
						conversation_log.extend(script_conversation_log)  # Add script's log to backend's log
						if not llm_move_san:
							raise ValueError("LLM script JSON output missing 'move'.")
					except json.JSONDecodeError:
						# Assume raw output is the move if not JSON (legacy script)
						conversation_log.append({"sender": "Backend", "type": "warning",
												 "content": "LLM script output was not valid JSON. Assuming raw output is the move."})
						llm_move_san = script_output_raw  # Fallback for non-JSON script output

					conversation_log.append({"sender": "Backend", "type": "move_received_from_script",
											 "content": f"Move from script: {llm_move_san}"})
				# (Validation logic as before, if needed)

				except subprocess.CalledProcessError as e:
					err_msg = f"Error executing LLM script: {e.stderr}"
					conversation_log.append({"sender": "Backend", "type": "error", "content": err_msg})
					return jsonify({'error': 'Error executing LLM script', 'details': e.stderr,
									'conversationLog': conversation_log}), 500
				except subprocess.TimeoutExpired:
					err_msg = "LLM script timed out."
					conversation_log.append({"sender": "Backend", "type": "error", "content": err_msg})
					return jsonify({'error': err_msg, 'conversationLog': conversation_log}), 500
				except ValueError as ve:  # Handles JSON parsing errors or missing move
					err_msg = f"Error processing LLM script output: {str(ve)}"
					conversation_log.append({"sender": "Backend", "type": "error", "content": err_msg})
					return jsonify({'error': err_msg, 'conversationLog': conversation_log}), 500
				except Exception as e:
					err_msg = f"Unexpected error calling LLM: {str(e)}"
					conversation_log.append({"sender": "Backend", "type": "error", "content": err_msg})
					return jsonify({'error': err_msg, 'conversationLog': conversation_log}), 500

			return jsonify({'move': llm_move_san, 'conversationLog': conversation_log})

		except Exception as e:
			err_msg = f"Overall error in /get-llm-move: {str(e)}"
			print(err_msg)  # Also print to server console for debugging
			conversation_log.append({"sender": "Backend", "type": "critical_error", "content": err_msg})
			return jsonify({'error': str(e), 'conversationLog': conversation_log}), 500

	port = cfg.pull('port', 5500)

	print("Starting Flask backend server...")
	status = 'ENABLED' if USE_BACKEND_STUB else 'DISABLED (attempts real LLM script unless "Random Mover" model is selected)'
	print(
		f"Backend stub mode default: {status}")
	app.run(host='0.0.0.0', port=port, debug=True)


##################


# Your existing AbstractGame and GameBase (with slight modifications for clarity/completeness)
class AbstractGame(AbstractTask):
	def load_from_request(self, data: JSONOBJ) -> JSONDATA:
		raise NotImplementedError("This method should be implemented in subclasses.")

	def generate_move(self, data: JSONOBJ, strategy: AbstractStrategy = None) -> JSONOBJ:
		raise NotImplementedError("This method should be implemented in subclasses.")

	def get_stub_response(self, data: JSONOBJ) -> Tuple[Any, List[JSONOBJ]]:
		"""Generates a stubbed/random move and a basic conversation log."""
		raise NotImplementedError("This method should be implemented for stubbed responses.")


# GameBase (from your snippet, with minor adjustments for the flow)
class GameBase(AbstractGame, fig.Configurable):
	def __init__(self, judge: Optional[AbstractJudge] = None, **kwargs):
		super().__init__(**kwargs)
		self.judge = judge

	def prepare(self, seed: int = None) -> None:
		pass

	def load_from_request(self, data: JSONOBJ) -> JSONDATA:
		"""Default: pass through data. Subclasses should extract specific game state."""
		return data

	def generate_move(self, data: JSONOBJ, strategy: AbstractStrategy) -> JSONOBJ:
		"""
		Take a step in the game using the provided strategy.
		`data` here is the raw request JSON.
		"""
		conversation_log_steps = []
		stats_log = {}

		# problem should be the specific game state (e.g., FEN, board string)
		# load_from_request extracts this from the broader 'data' (request JSON)
		problem_representation = self.load_from_request(data)
		conversation_log_steps.append({"sender": "Backend", "type": "internal_state_loaded",
									   "content": f"Problem loaded: {type(problem_representation).__name__}"})

		side_info = self.task.side_information(problem_representation)  # task is self
		if side_info is not None:
			conversation_log_steps.append({"sender": "Backend", "type": "side_information", "content": side_info})

		question_for_llm = self.observe(problem_representation)  # task is self
		conversation_log_steps.append(
			{"sender": "Backend (to LLM)", "type": "question_formulated", "content": question_for_llm})

		raw_llm_response_text = ""
		llm_steps_details = {}
		failed = False

		if not strategy:  # Should not happen if logic is correct in route
			raise ValueError("Strategy not provided to generate_move")

		with strategy.collect_stats() as stats:
			try:
				raw_llm_response_text, llm_steps_details_tuple = strategy.solve(question_for_llm,
																				side_information=side_info)
				if isinstance(llm_steps_details_tuple, dict):  # Assuming solve might return steps
					llm_steps_details = llm_steps_details_tuple
				elif llm_steps_details_tuple is not None:
					llm_steps_details = {"llm_internal_steps": llm_steps_details_tuple}


			except StrategyFailure as e:
				raw_llm_response_text = str(e) if type(e) == StrategyFailure else f'{e.__class__.__name__}: {e}'
				llm_steps_details = {'error': type(e).__name__, 'error_message': str(e),
									 'traceback': traceback.format_exc()}
				failed = True
			except Exception as e:  # Catch other unexpected strategy errors
				raw_llm_response_text = f"Unexpected strategy error: {e.__class__.__name__}: {e}"
				llm_steps_details = {'error': type(e).__name__, 'error_message': str(e),
									 'traceback': traceback.format_exc()}
				failed = True

		if len(stats):  # Assuming stats is a dict-like object from context manager
			stats_log.update(dict(stats))  # Ensure it's a plain dict

		conversation_log_steps.append({"sender": "LLM", "type": "raw_response", "content": raw_llm_response_text})
		if llm_steps_details:
			conversation_log_steps.append(
				{"sender": "LLM Internal", "type": "processing_steps", "content": llm_steps_details})

		decision = None
		judgement_details = {}

		if failed:
			decision = None  # Or some error indicator
			conversation_log_steps.append(
				{"sender": "Backend", "type": "judgement_error", "content": "Strategy failed to produce a response."})
		elif self.judge is None and not self.task.is_judge:  # task is self
			decision = raw_llm_response_text  # No judge, decision is raw response (strategy must format it as a move)
			conversation_log_steps.append({"sender": "Backend", "type": "judgement_passthrough",
										   "content": "No judge configured; using raw LLM response as decision."})
		else:
			if self.judge is None:  # Game itself is the judge
				_verdict, decision, judgement_details_dict = self.task.evaluate(raw_llm_response_text,
																				problem_representation,
																				side_info)  # task is self
				if isinstance(judgement_details_dict, dict): judgement_details = judgement_details_dict
			else:  # External judge
				with self.judge.collect_stats() as judge_stats_cm:
					# interpret might return (decision, details_dict) or just decision
					judge_output = self.judge.interpret(question_for_llm, raw_llm_response_text)
					if isinstance(judge_output, tuple) and len(judge_output) == 2:
						decision, judgement_details_dict = judge_output
						if isinstance(judgement_details_dict, dict): judgement_details = judgement_details_dict
					else:
						decision = judge_output  # Assume only decision is returned

				if len(judge_stats_cm):  # Assuming judge_stats_cm is dict-like
					stats_log['judge'] = dict(judge_stats_cm)

			conversation_log_steps.append({"sender": "Judge", "type": "interpretation",
										   "content": judgement_details or f"Processed decision: {decision}"})

		return {
			"decision": decision,  # This is the actual game move (e.g., SAN, index)
			"conversation_log_steps": conversation_log_steps,  # Detailed steps for the log
			"stats": stats_log,
			# Other details from proc if needed by the route
			"question_to_llm": question_for_llm,
			"raw_llm_response": raw_llm_response_text,
		}


@fig.component('chess')
class ChessGame(GameBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		# python-chess board instance, will be created in load_from_request
		self.board = None
		# Chess game itself can act as a judge to validate/convert LLM move
		self.is_judge_override = True  # Custom attribute to signal this

	@property
	def is_judge(self):  # So GameBase sees it
		return getattr(self, 'is_judge_override', False)

	def load_from_request(self, data: JSONOBJ) -> JSONOBJ:
		"""Loads FEN and player to move for Chess."""
		fen = data.get('fen', 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')  # Default to start
		player_to_move = data.get('player_to_move', 'white')  # 'white' or 'black'

		import chess  # Import here to ensure it's available when ChessGame is used
		self.board = chess.Board(fen)

		# Ensure the turn in the FEN matches player_to_move if provided, or use FEN's turn
		expected_turn_char = 'w' if player_to_move.lower() == 'white' else 'b'
		if self.board.turn != (expected_turn_char == 'w'):
			print(
				f"Warning: Mismatch between FEN turn ({'white' if self.board.turn else 'black'}) and player_to_move ('{player_to_move}'). Using FEN's turn.")

		return {"fen": self.board.fen(), "current_player_color": "white" if self.board.turn else "black"}

	def observe(self, problem: JSONOBJ) -> str:
		"""The 'question' for the LLM is the FEN and whose turn."""
		# Problem here is the output of load_from_request
		return f"Current FEN: {problem['fen']}. It is {problem['current_player_color']}'s turn. What is your move in SAN or UCI notation?"

	def evaluate(self, llm_response: str, problem: JSONOBJ, side_info: Optional[JSONOBJ]) -> Tuple[
		bool, Optional[str], JSONOBJ]:
		"""
		Acts as a judge. Tries to parse LLM response as a chess move.
		Returns: (is_valid_move, move_san_or_uci, judgement_details_dict)
		"""
		if not self.board:  # Should be set by load_from_request via generate_move
			self.board = chess.Board(problem['fen'])

		details = {"llm_raw_output_received": llm_response}
		try:
			# Try to parse as SAN first, then UCI. chess.js on frontend is sloppy.
			move = self.board.parse_san(llm_response)
			details["parsed_as"] = "SAN"
			details["move_object"] = str(move)
			return True, self.board.san(move), details  # Return standard SAN
		except chess.InvalidMoveError:  # ValueError for SAN
			try:
				move = self.board.parse_uci(llm_response)
				details["parsed_as"] = "UCI"
				details["move_object"] = str(move)
				# Frontend chess.js can handle UCI, so return it if SAN fails
				return True, move.uci(), details
			except chess.InvalidMoveError:  # ValueError for UCI
				details["error"] = "LLM response is not a valid SAN or UCI move for the current position."
				details["legal_moves_example"] = [self.board.san(m) for m in list(self.board.legal_moves)[:3]]
				return False, None, details
		except Exception as e:  # Other parsing errors
			details["error"] = f"Unexpected error parsing LLM move: {str(e)}"
			return False, None, details

	def get_stub_response(self, data: JSONOBJ) -> Tuple[Optional[str], List[JSONOBJ]]:
		problem = self.load_from_request(data)  # Sets self.board
		log = [{"sender": "Backend Stub", "type": "info",
				"content": f"Chess stub generating random move for FEN: {problem['fen']}"}]

		if self.board.is_game_over():
			log.append({"sender": "Backend Stub", "type": "info", "content": "Game is over, no moves."})
			return None, log

		legal_moves = list(self.board.legal_moves)
		if not legal_moves:
			log.append({"sender": "Backend Stub", "type": "info", "content": "No legal moves."})
			return None, log

		import random
		move = random.choice(legal_moves)
		move_san = self.board.san(move)
		log.append({"sender": "Backend Stub", "type": "decision", "content": f"Stub chose move: {move_san}"})
		return move_san, log


@fig.component('tictactoe')
class TicTacToeGame(GameBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.board_state = list("_________")  # ['X', '_', 'O', ...]
		self.current_player = 'X'
		self.is_judge_override = True

	@property
	def is_judge(self):
		return getattr(self, 'is_judge_override', False)

	def load_from_request(self, data: JSONOBJ) -> JSONOBJ:
		"""Loads board_state string and player to move for TTT."""
		board_str = data.get('board_state', "_________")
		self.current_player = data.get('player_to_move', 'X').upper()

		if len(board_str) == 9 and all(c in 'XO_' for c in board_str.upper()):
			self.board_state = list(board_str.upper())
		else:
			self.board_state = list("_________")  # Default to empty on invalid input
			print(f"Warning: Invalid TTT board_state '{board_str}', defaulting to empty.")

		return {"board_array": self.board_state.copy(), "current_player_char": self.current_player}

	def observe(self, problem: JSONOBJ) -> str:
		"""The 'question' for the LLM for TTT."""
		board_display = "".join(problem['board_array'])
		return (f"Tic-Tac-Toe board: {board_display} (X, O, _ for empty). "
				f"It is player {problem['current_player_char']}'s turn. "
				f"Which cell index (0-8, top-left to bottom-right) do you choose?")

	def _check_ttt_winner(self, board_arr):
		lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
		for i, j, k in lines:
			if board_arr[i] != '_' and board_arr[i] == board_arr[j] == board_arr[k]:
				return board_arr[i]
		if '_' not in board_arr: return 'DRAW'
		return None

	def evaluate(self, llm_response: str, problem: JSONOBJ, side_info: Optional[JSONOBJ]) -> Tuple[
		bool, Optional[int], JSONOBJ]:
		"""
		Acts as a judge for TTT. Tries to parse LLM response as a cell index.
		Returns: (is_valid_choice, move_index_int, judgement_details_dict)
		"""
		details = {"llm_raw_output_received": llm_response}
		try:
			# Try to extract a single digit 0-8
			import re
			match = re.search(r'\b([0-8])\b', llm_response)
			if match:
				move_index = int(match.group(1))
				# problem['board_array'] has the state when observe was called
				if 0 <= move_index <= 8 and problem['board_array'][move_index] == '_':
					details["parsed_as"] = "valid_index"
					details["chosen_index"] = move_index
					return True, move_index, details
				else:
					details["error"] = f"Index {move_index} is invalid or cell is already taken."
					details["board_at_decision"] = "".join(problem['board_array'])
					return False, None, details
			else:
				details["error"] = "LLM response does not contain a valid cell index (0-8)."
				return False, None, details
		except Exception as e:
			details["error"] = f"Unexpected error parsing LLM move index: {str(e)}"
			return False, None, details

	def get_stub_response(self, data: JSONOBJ) -> Tuple[Optional[int], List[JSONOBJ]]:
		problem = self.load_from_request(data)  # Sets self.board_state and self.current_player
		log = [{"sender": "Backend Stub", "type": "info",
				"content": f"TTT stub for {''.join(problem['board_array'])} player {problem['current_player_char']}"}]

		if self._check_ttt_winner(problem['board_array']):  # Game over
			log.append({"sender": "Backend Stub", "type": "info", "content": "Game is over, no moves."})
			return None, log

		available_indices = [i for i, cell in enumerate(problem['board_array']) if cell == '_']
		if not available_indices:
			log.append({"sender": "Backend Stub", "type": "info", "content": "No available moves (draw)."})
			return None, log

		import random
		chosen_index = random.choice(available_indices)
		log.append({"sender": "Backend Stub", "type": "decision", "content": f"Stub chose cell index: {chosen_index}"})
		return chosen_index, log


