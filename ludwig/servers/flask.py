from ..imports import *
import traceback  # Added for GameBase
from typing import Optional, List, Tuple, Any  # Added for type hints
import chess

# Mocking abstract classes for standalone execution if not provided
# In your actual project, these would be imported.
from ..abstract import AbstractStrategy, AbstractJudge, AbstractTask, JSONDATA, JSONOBJ
from ..errors import StrategyFailure
from ..util import vllm_Client, AbstractClient, PromptTemplate


class GameBase(fig.Configurable):
	def prepare(self,):
		pass

	def possible_actions(self, state: JSONDATA) -> List[JSONDATA]:
		raise NotImplementedError

	def update_state(self, state: JSONDATA, action: JSONDATA, allow_violations: bool = False) -> JSONDATA:
		raise NotImplementedError


class ChessGame(GameBase):
	def possible_actions(self, state: JSONOBJ) -> List[str]:
		fen = state['fen']
		active_player = state['player_to_move']
		board = chess.Board(fen)
		if active_player == 'white':
			actions = [move.uci() for move in board.legal_moves if board.turn == chess.WHITE]
		else:
			actions = [move.uci() for move in board.legal_moves if board.turn == chess.BLACK]
		return actions

	def update_state(self, state: JSONOBJ, action: str, allow_violations: bool = False) -> JSONOBJ:
		fen = state['fen']
		active_player = state['player_to_move']
		board = chess.Board(fen)
		move = chess.Move.from_uci(action)
		if move not in board.legal_moves:
			if allow_violations:
				board.push(move)
			else:
				raise StrategyFailure(f"Illegal move attempted: {action}")
		else:
			board.push(move)
		state['fen'] = board.fen()
		state['player_to_move'] = 'black' if active_player == 'white' else 'white'
		return state


class TicTacToeGame(GameBase):
	def possible_actions(self, state: Tuple[str, str]) -> List[str]:
		board = state['board']
		# active_player = state['player_to_move']

		actions = [ i for i in range(9) if board[i] == '_' ]
		return actions

	def update_state(self, state: JSONOBJ, action: int, allow_violations: bool = False) -> JSONOBJ:
		board = state['board']
		board = list(board)  # Convert string to list for mutability
		active_player = state['player_to_move']
		if board[action] != '_':
			if allow_violations:
				board[action] = active_player
			else:
				raise StrategyFailure(f"Illegal move attempted: {action}")
		else:
			board[action] = active_player
		board = ''.join(board)  # Convert list back to string
		state['board'] = board
		state['player_to_move'] = 'O' if active_player == 'X' else 'X'
		return state



class PlayerBase(fig.Configurable):
	def prepare(self):
		pass
	def next_state(self, client: AbstractClient, game: GameBase, state: JSONDATA, log: list[dict[str,str]],
				   judge: Optional[AbstractClient] = None):
		raise NotImplementedError

	def encode_state(self, state: JSONDATA) -> str:
		raise NotImplementedError

	def decode_state(self, state_str: str) -> JSONDATA:
		raise NotImplementedError


# @fig.component('player/state')
class SimplePlayer(PlayerBase):
	def __init__(self, template: str = '{state}', params: JSONOBJ = {},
				 judge_template: str = None, judge_continue: bool = True, **kwargs):
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		if judge_template is not None and not isinstance(judge_template, PromptTemplate):
			judge_template = PromptTemplate(judge_template)
		super().__init__(**kwargs)
		self.params = params
		self.template = template
		self.judge_template = judge_template
		self.judge_continue = judge_continue

	def encode_state(self, state: JSONDATA) -> str:
		raise NotImplementedError

	def decode_state(self, state_str: str) -> JSONDATA:
		raise NotImplementedError

	def validate_action(self, action: JSONDATA, actions: List[JSONDATA]) -> JSONDATA:
		raise NotImplementedError

	def next_state(self, client: AbstractClient, game: GameBase, state: JSONDATA, log: list[dict[str, str]],
				   judge: Optional[AbstractClient] = None):
		state_str = self.encode_state(state)
		player = state['player_to_move']
		actions = game.possible_actions(state)
		prompt = self.template.fill(state=state_str, player=player, actions=actions)

		chat = client.begin_chat(prompt)
		client.step(chat, **self.params)
		response = chat[-1]['content']

		log.append({"sender": "Backend", "type": "prompt", "content": prompt})
		log.append({"sender": "LLM", "type": "response", "content": response})

		if self.judge_template:
			if judge is None:
				judge = client
			judge_prompt = self.judge_template.fill(response=response, state=state_str, player=player, actions=actions)
			judge_params = dict(grammar=[str(a) for a in actions], max_tokens=10)
			if self.judge_continue:
				chat.append({'role': 'user', 'content': judge_prompt})
				judge.step(chat, **judge_params)
				judge_response = chat[-1]['content']
			else:
				judge_response = judge.get_response(judge_prompt, **judge_params)
			log.append({"sender": "Judge", "type": "judge", "content": judge_response})
			raw_action = judge_response
		else:
			# use regex to find the action (defined as the last digit in the response)
			import re
			match = re.search(r'\b(\d+)\b', response[::-1])
			if match:
				raw_action = match.group(1)
				log.append({"sender": "Judge", "type": "judge", "content": raw_action})
			else:
				raw_action = response.strip()

		action = self.validate_action(raw_action, actions)
		new_state = game.update_state(state, action)
		return new_state


@fig.component('ttt/simple')
class TTT_Simple(SimplePlayer):
	def __init__(self, params: JSONOBJ = {}, template: str = 'game/ttt/simple',
				 judge_template: str = 'game/ttt/judge', judge_continue = False, **kwargs):
		super().__init__(params=params, template=template, judge_template=judge_template,
						 judge_continue=judge_continue, **kwargs)

	def encode_state(self, state: JSONDATA) -> str:
		options = []
		index = 1
		for v in state['board']:
			if v == '_':
				options.append(str(index))
				index += 1
			else:
				options.append(v)
		# options = [v if v != '_' else i+1 for i, v in enumerate(state['board'])]
		nested = [options[i:i + 3] for i in range(0, 9, 3)]
		state_str = tabulate(nested, tablefmt='grid', stralign='center')
		return state_str

	def decode_state(self, state_str: str) -> JSONDATA:
		return {'board': state_str, 'player_to_move': 'X'}

	def validate_action(self, action: str, actions: List[int]) -> int:
		return actions[int(action.strip()) - 1]


@fig.component('chess/simple')
class Chess_Simple(SimplePlayer):
	pass


@fig.script('backend', description='Launch demo backend flask server to bridge the LLMs.')
def launch_backend(cfg: fig.Configuration):

	client_names = {
		'meta-llama/Llama-3.1-8B-Instruct': 'llama8b',
		'google/gemma-3-27b-it': 'gemma3',
		'meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8': 'maverick',
		'meta-llama/Llama-4-Scout-17B-16E-Instruct': 'scout',
	}

	params = cfg.pull('params', {})

	raw_clients = cfg.pull('clients', [])
	assert len(raw_clients)
	clients = {}
	for client in raw_clients:
		if isinstance(client, (str, int)):
			client = vllm_Client(addr=client)
		else:
			assert isinstance(client, AbstractClient)
		client.prepare()
		ident = client.ident
		if ident in client_names:
			ident = client_names[ident]
		clients[ident] = client

	print(f'{len(clients)} clients: {", ".join(clients.keys())}')

	judge = cfg.pull('judge', None)
	if judge is not None and not isinstance(judge, AbstractClient):
		judge = vllm_Client(addr=judge)
	if judge is not None:
		judge.prepare()

	games = {
		'chess': ChessGame(),
		'tictactoe': TicTacToeGame(),
	}
	for game in games.values():
		game.prepare()

	games_map = cfg.pulls('games', 'games', default=games)  # Assuming this returns dict {name: GameInstance}

	players = cfg.pull('players', {})  # Assuming this returns dict {name: StrategyInstance}
	if not len(players): raise ValueError("No players configured.")
	for player in players.values():
		if isinstance(player, PlayerBase):
			player.prepare()

	from flask import Flask, request, jsonify
	from flask_cors import CORS
	# chess and random imported within game classes where needed
	# subprocess and json for external script are not used if strategies handle LLM calls

	app = Flask(__name__)
	CORS(app)

	USE_BACKEND_STUB_CONFIG = cfg.pull('use_global_stub', False)  # Global stub flag from config

	available_clients_list = [{'id': key, 'name': c.ident if hasattr(c, 'ident') else key} for key, c in
							  clients.items()]
	available_strategies_list = [{'id': key, 'name': key} for key, s in players.items()]

	# # Add a simple stub option to the lists for the frontend
	# # This is conceptual, your frontend might handle "Use Frontend Stub" checkbox separately
	# # or you might have a dedicated "stub_strategy" or "stub_client"
	# # For now, let's assume a special model ID can trigger stub mode
	STUB_MODEL_ID = "random"
	if not any(m['id'] == STUB_MODEL_ID for m in available_clients_list):
		available_clients_list.append({'id': STUB_MODEL_ID, 'name': "Random Move"})

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

			game = games_map[game_id]

			selected_model_id = data.get('selected_model_id')
			selected_strategy_id = data.get(
				'selected_prompting_method_id')  # Renamed from selected_prompt_id for clarity

			# conversation_log.append({"sender": "Backend", "type": "request_info",
			# 			"content": f"Game: {game_id}, Model: {selected_model_id}, Strategy: {selected_strategy_id}"})

			if selected_model_id == STUB_MODEL_ID:
				game_state = data.get('game_state')
				actions = game.possible_actions(game_state)
				action = random.choice(actions)
				conversation_log.append({"sender": "Backend", "type": "response",
										 'content': f'Selected random action: {action}'})
				new_state = game.update_state(game_state, action, allow_violations=True)
				return jsonify({'new_state': new_state, 'conversationLog': conversation_log})

			player = players.get(selected_strategy_id, {}).get(game_id)
			client = clients.get(selected_model_id)

			if not player:
				return jsonify({'error': f'Invalid or missing strategy: {selected_strategy_id}',
								'conversationLog': [{"sender": "Backend", "type": "error",
													"content": f"Unknown strategy: {selected_strategy_id}"}]}), 400

			game_state = data.get('game_state')
			new_state = player.next_state(client, game, game_state, conversation_log, judge=judge)

			return jsonify({'new_state': new_state, 'conversationLog': conversation_log})

			# return jsonify({'new_state': new_state, 'action': action, 'conversationLog': conversation_log})

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
	debug_mode = False

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




