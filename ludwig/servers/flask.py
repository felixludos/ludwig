import traceback  # Added for GameBase
from typing import Optional, List, Tuple, Any  # Added for type hints
import fig  # Assuming fig is your configuration library, used as per your snippet

# Mocking abstract classes for standalone execution if not provided
# In your actual project, these would be imported.
from ..abstract import AbstractStrategy, AbstractJudge, AbstractTask, JSONDATA, JSONOBJ
from ..errors import StrategyFailure


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


@fig.script('bridge', description='Launch demo backend flask server to bridge the LLMs.')
def launch_bridge(cfg: fig.Configuration):
	games_config = cfg.pull('games', {})  # Changed variable name to avoid conflict
	if not games_config:
		raise ValueError("No games configured. Please provide 'games' in config.")

	# Instantiate game objects
	# Ensure `fig.Configurable` correctly instantiates based on config type
	# This might look like: games_map = {name: fig.create(conf) for name, conf in games_config.items()}
	# For this example, I'll manually create them if they match known types
	games_map = {}
	for name, game_conf_data in games_config.items():
		if name == 'chess':  # Assuming 'chess' is the key in your config for ChessGame
			games_map[name] = ChessGame(**game_conf_data.get('params', {}))  # Pass params if any
		elif name == 'tictactoe':
			games_map[name] = TicTacToeGame(**game_conf_data.get('params', {}))
		else:
			# If using fig.create for general components:
			# games_map[name] = fig.create(game_conf_data)
			# This requires your config to specify the class type, e.g. by a '_target_' key
			print(f"Warning: Unknown game type '{name}' in config. Manual instantiation needed or use fig.create.")
		# Fallback for testing if fig.create is not how it works for you
		# games_map[name] = fig.Configurable(**game_conf_data) # Generic configurable

	for game_instance in games_map.values():
		if hasattr(game_instance, 'prepare'):
			game_instance.prepare()

	clients = cfg.pull('clients', {})
	if not len(clients): raise ValueError("No clients configured.")
	for c_name, c_conf in clients.items():  # Assuming clients is a dict {name: ClientConfig}
		if isinstance(c_conf, fig.Configurable): c_conf.prepare()
	# If c_conf are already client instances, no prepare needed unless they have it.
	# This part depends heavily on your 'fig' library structure.
	# For simplicity, let's assume 'clients' from config are already prepared or don't need it.

	strats = cfg.pulls('strategies', 'strats', default={})  # Assuming this returns dict {name: StrategyInstance}
	if not len(strats): raise ValueError("No strategies configured.")
	for s_instance in strats.values():
		if hasattr(s_instance, 'prepare'): s_instance.prepare()

	from flask import Flask, request, jsonify
	from flask_cors import CORS
	# chess and random imported within game classes where needed
	# subprocess and json for external script are not used if strategies handle LLM calls

	app = Flask(__name__)
	CORS(app)

	USE_BACKEND_STUB_CONFIG = cfg.pull('use_global_stub', False)  # Global stub flag from config

	available_clients_list = [{'id': key, 'name': c.ident if hasattr(c, 'ident') else key} for key, c in
							  clients.items()]
	available_strategies_list = [{'id': key, 'name': s.ident if hasattr(s, 'ident') else key} for key, s in
								 strats.items()]

	# Add a simple stub option to the lists for the frontend
	# This is conceptual, your frontend might handle "Use Frontend Stub" checkbox separately
	# or you might have a dedicated "stub_strategy" or "stub_client"
	# For now, let's assume a special model ID can trigger stub mode
	STUB_MODEL_ID = "stub_model_random"
	if not any(m['id'] == STUB_MODEL_ID for m in available_clients_list):
		available_clients_list.append({'id': STUB_MODEL_ID, 'name': "Random Mover (Backend Stub)"})

	@app.route('/get-llm-settings-options', methods=['GET'])
	def get_llm_settings_options_route():
		game_id_query = request.args.get('game', 'default')
		# Potentially filter models/strategies by game_id_query if applicable
		return jsonify({
			"models": available_clients_list,  # In a real app, might filter by game
			"prompting_methods": available_strategies_list  # In a real app, might filter by game
		})

	@app.route('/get-llm-move', methods=['POST'])
	def get_llm_move_route():
		conversation_log = []
		try:
			data = request.json
			game_id = data.get('game_id')  # Expect 'game_id' from frontend
			if not game_id or game_id not in games_map:
				return jsonify({'error': f'Invalid or missing game_id: {game_id}', 'conversationLog': [
					{"sender": "Backend", "type": "error", "content": f"Unknown game: {game_id}"}]}), 400

			game_instance = games_map[game_id]

			selected_model_id = data.get('selected_model_id')
			selected_strategy_id = data.get(
				'selected_prompting_method_id')  # Renamed from selected_prompt_id for clarity

			conversation_log.append({"sender": "Backend", "type": "request_info",
									 "content": f"Game: {game_id}, Model: {selected_model_id}, Strategy: {selected_strategy_id}"})

			llm_move_formatted = None

			# Determine if stub should be used
			use_stub_for_this_request = USE_BACKEND_STUB_CONFIG or (selected_model_id == STUB_MODEL_ID)

			if use_stub_for_this_request:
				conversation_log.append(
					{"sender": "Backend", "type": "mode_info", "content": "Using backend stub logic."})
				move_data, stub_log_entries = game_instance.get_stub_response(data)  # Pass full request data
				llm_move_formatted = move_data
				conversation_log.extend(stub_log_entries)
			else:
				strategy_instance = strats.get(selected_strategy_id)
				client_instance = clients.get(selected_model_id)

				if not strategy_instance:
					return jsonify({'error': f'Strategy {selected_strategy_id} not found.',
									'conversationLog': conversation_log}), 400
				if hasattr(strategy_instance, 'client') and client_instance:  # If strategy uses a client property
					strategy_instance.client = client_instance
				elif hasattr(strategy_instance, 'set_client') and client_instance:  # Or a setter method
					strategy_instance.set_client(client_instance)

				conversation_log.append({"sender": "Backend", "type": "mode_info", "content": "Using LLM strategy."})

				# game.generate_move expects the raw request data, its internal load_from_request will parse it
				processing_result = game_instance.generate_move(data, strategy_instance)

				llm_move_formatted = processing_result.get('decision')
				if "conversation_log_steps" in processing_result:
					conversation_log.extend(processing_result["conversation_log_steps"])
				if "stats" in processing_result and processing_result["stats"]:
					conversation_log.append(
						{"sender": "Backend", "type": "stats_summary", "content": processing_result["stats"]})

			# Check if the game itself determined the game is over (e.g. by stub move making a win)
			# This part is tricky as game state isn't explicitly updated *within* this route yet after a move
			# The game_instance methods should ideally handle their internal state.
			# The frontend will re-evaluate game over after receiving the move.

			return jsonify({'move': llm_move_formatted, 'conversationLog': conversation_log})

		except Exception as e:
			err_msg = f"Overall error in /get-llm-move: {str(e)}"
			detailed_traceback = traceback.format_exc()
			print(f"{err_msg}\n{detailed_traceback}")
			conversation_log.append({"sender": "Backend", "type": "critical_error", "content": err_msg,
									 "details": detailed_traceback if cfg.pull('debug_mode',
																			   False) else "Traceback hidden"})
			return jsonify({'error': str(e), 'conversationLog': conversation_log}), 500

	port = cfg.pull('port', 5001)  # Default to 5001 if not in config
	debug_mode = cfg.pull('debug_mode', True)  # Default to True for development

	print(f"Starting Flask backend server on port {port} (Debug: {debug_mode})...")
	print(f"Global stub mode: {'ENABLED' if USE_BACKEND_STUB_CONFIG else 'DISABLED'}")
	print(f"Available games: {list(games_map.keys())}")
	print(f"Available clients: {[c['name'] for c in available_clients_list]}")
	print(f"Available strategies: {[s['name'] for s in available_strategies_list]}")

	app.run(host='0.0.0.0', port=port, debug=debug_mode)

# Example fig.Configuration structure this script might expect:
# {
#   "games": {
#     "chess": {"_target_": "your_module.ChessGame", "params": {}}, // If using fig.create style
#     "tictactoe": {"_target_": "your_module.TicTacToeGame", "params": {}}
#     // Or if you manually instantiate like in my example:
#     // "chess": {},
#     // "tictactoe": {}
#   },
#   "clients": {
#     "gpt4": {"_target_": "some_llm_client.GPT4Client", "api_key": "YOUR_KEY", "ident": "GPT-4 Turbo"},
#     "claude3": {"_target_": "some_llm_client.ClaudeClient", "api_key": "YOUR_KEY", "ident": "Claude 3 Opus"}
#   },
#   "strategies": { // or "strats" depending on your cfg.pulls
#     "simple_prompt": {"_target_": "your_strategies.SimplePromptStrategy", "template": "Play the best move: {question}", "ident": "Simple Prompt"},
#     "cot_prompt": {"_target_": "your_strategies.ChainOfThoughtStrategy", "ident": "Chain-of-Thought"}
#   },
#   "port": 5001,
#   "use_global_stub": False,
#   "debug_mode": True
# }




