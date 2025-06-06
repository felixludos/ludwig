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