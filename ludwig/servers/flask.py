from ..imports import *
import traceback  # Added for GameBase
from typing import Optional, List, Tuple, Any  # Added for type hints
import chess
import re

from pprint import pprint  # Added for pretty printing

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


	def encode_state(self, state: JSONDATA) -> JSONDATA:
		raise NotImplementedError

	def decode_state(self, obs: JSONDATA, state: JSONDATA) -> JSONDATA:
		raise NotImplementedError

	def encode_action(self, action: JSONDATA, state: JSONDATA, actions: List[JSONDATA] = None) -> JSONDATA:
		raise NotImplementedError

	def decode_action(self, choice: JSONDATA, state: JSONDATA, actions: List[JSONDATA] = None) -> JSONDATA:
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

	def encode_state(self, state: JSONDATA) -> JSONDATA:
		fen = state['fen']
		active_player = state['player_to_move']

		actions = self.possible_actions(state)

		return {'options': ', '.join(actions), 'fen': fen, 'active': active_player}

	def decode_state(self, obs: JSONDATA, state: JSONDATA) -> JSONDATA:
		# validate fen format
		fen = obs#['fen']
		return {'fen': fen, 'player_to_move': 'white' if state['player_to_move'] == 'black' else 'black'}

	def encode_action(self, action: JSONDATA, state: JSONDATA, actions: List[JSONDATA] = None) -> JSONDATA:
		return action

	def decode_action(self, choice: JSONDATA, state: JSONDATA, actions: List[JSONDATA] = None) -> JSONDATA:
		return choice


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

	def encode_state(self, state: str) -> JSONDATA:
		state_str = state['board'].replace('_', '.')
		state_str = [list(state_str[i:i + 3]) for i in range(0, 9, 3)]
		state_str = '\n'.join(' '.join(row) for row in state_str)
		# state_str = tabulate(state_str, tablefmt='grid', stralign='center')
		# state_str = str(state_str)

		options = []
		index = 1
		for v in state['board']:
			if v == '_':
				options.append(str(index))
				# options.append(index)
				index += 1
			else:
				options.append(v)
		# options = [v if v != '_' else i+1 for i, v in enumerate(state['board'])]
		options_str = [options[i:i + 3] for i in range(0, 9, 3)]
		# options_str = tabulate(options_str, tablefmt='grid', stralign='center')
		# options_str = '\n'.join(''.join(row) for row in options_str)
		options_str = '\n'.join(' '.join(row) for row in options_str)
		# options_str = str(options_str)
		return {'board': state_str, 'options': options_str, 'active': state['player_to_move']}

	def decode_state(self, obs: str, state: JSONDATA) -> JSONDATA:
		raw = obs#['board']

		board = raw.replace('/', '').replace(' ', '').replace('.', '_')

		return {'board': board, 'player_to_move': 'X' if state['player_to_move'] == 'O' else 'O'}

	def encode_action(self, action: JSONDATA, state: JSONDATA, actions: List[JSONDATA] = None) -> JSONDATA:
		return str(actions.index(action) + 1)

	def decode_action(self, choice: str, state: JSONDATA, actions: List[JSONDATA] = None) -> JSONDATA:
		return actions[int(choice.strip()) - 1]  # Convert to zero-based index



class PlayerBase(fig.Configurable):
	def prepare(self):
		pass
	def next_state(self, client: AbstractClient, game: GameBase, state: JSONDATA, log: list[dict[str,str]],
				   judge: Optional[AbstractClient] = None):
		raise NotImplementedError



@fig.component('simple')
class SimplePlayer(PlayerBase):
	def __init__(self, template: str, pattern: str = None, mode: str = 'state', params: JSONOBJ = None,
				 judge_template: str = None, judge_chat: bool = False,
				 grammar: str = None, **kwargs):
		if not isinstance(template, PromptTemplate):
			template = PromptTemplate(template)
		if params is None:
			params = {}
		if judge_template is not None and not isinstance(judge_template, PromptTemplate):
			judge_template = PromptTemplate(judge_template)
		if pattern == 'ttt':
			pattern = "[XO\.] [XO\.] [XO\.] / [XO\.] [XO\.] [XO\.] / [XO\.] [XO\.] [XO\.]"
		# if pattern == 'fen':
		# 	pattern = '([rnbqkpRNBQKP1-8]+\/){7}[rnbqkpRNBQKP1-8]+\s[wb]\s(-|[KQkq]{1,4})\s(-|[a-h][36])\s\d+\s\d+'
		# 	# pattern = r'([rnbqkpRNBQKP1-8]{1,8}/){7}[rnbqkpRNBQKP1-8]{1,8}\s[bw]\s(-|K?Q?k?q?)\s(-|[a-h][36])\s\d+\s\d+'
		if grammar is None:
			grammar = pattern
		super().__init__(**kwargs)
		assert mode in ('state', 'action'), f'Unknown mode: {mode}'
		self.client, self._judge = None, None
		self.mode = mode
		self.params = params
		self.template = template
		self.judge_template = judge_template
		self.judge_chat = judge_chat
		self.pattern = pattern
		self.grammar = grammar

	@property
	def ident(self):
		return self.mode

	@property
	def judge(self):
		return self._judge or self.client
	@judge.setter
	def judge(self, judge: AbstractClient):
		self._judge = judge

	def _judge_grammar(self, state: JSONDATA, actions: List[JSONDATA]) -> Optional[JSONDATA]:
		pass

	@staticmethod
	def _find_last(pattern: str, text: str) -> Optional[str]:
		"""
		Find the last occurrence of a pattern in the text.
		"""
		matches = re.findall(pattern, text)
		if matches:
			return matches[-1]
		return None

	def ask_player(self, game: GameBase, obs: JSONDATA, choices: List[JSONDATA],
				   log: List[Dict[str, str]], **kwargs) -> List[Dict[str,str]]:
		"""
		Ask the player for their decision based on the current state.
		"""
		prompt = self.template.fill(player=self, game=game, state=obs, actions=choices)

		log.append({"sender": "Backend", "type": "prompt", "content": prompt})

		params = {**self.params, **kwargs}
		chat = self.client.begin_chat(prompt)
		self.client.step(chat, **params)
		response = chat[-1]['content']

		# log.append({"sender": "Backend", "type": "prompt", "content": prompt})

		full_response = response
		if 'reasoning_content' in chat[-1]:
			full_response = f'<think>\n{chat[-1]["reasoning_content"]}\n</think>\n\n{response}'
		log.append({"sender": "LLM", "type": "response", "content": full_response})

		return chat

	def next_state(self, client: AbstractClient, game: GameBase, state: JSONDATA, log: list[dict[str, str]],
				   judge: Optional[AbstractClient] = None):
		self.client = client
		self.judge = judge
		observation = game.encode_state(state)
		actions = game.possible_actions(state)
		choices = [game.encode_action(a, state, actions) for a in actions]
		chat = self.ask_player(game, observation, choices, log)

		verdict = self.ask_judge(chat, game, observation, choices, log)

		if self.mode == 'action':
			action = game.decode_action(verdict, state, actions)
			new_state = game.update_state(state, action)
		elif self.mode == 'state':
			new_state = game.decode_state(verdict, state)
		else:
			raise ValueError(f'Unknown mode: {self.mode}')

		# self.client = None
		# self.judge = None
		return new_state

	def ask_judge(self, chat: List[Dict[str, str]], game: JSONDATA, obs: JSONDATA, choices: List[JSONDATA],
				  log: List[Dict[str, str]], **kwargs) -> JSONDATA:
		response = chat[-1]['content']

		if self.judge_template is None:
			if self.mode == 'action':
				all_choices = "|".join(choices)
				pattern = rf"\b({all_choices})\b"
			else:
				pattern = self.pattern
			if pattern == 'fen':
				line = response.replace('`', '').strip().split('\n')[-1].replace('**', '').replace(':', '')
				if 'fen' in line.lower():
					line = line.split('fen')[-1].split('FEN')[-1].strip()

				verdict = line.strip()
			else:
				verdict = self._find_last(pattern, response)

			log.append({"sender": "Judge", "type": "matching", "content": verdict})

		else:
			judge_prompt = self.judge_template.fill(player=self, game=game, response=response,
													state=obs, actions=choices)
			judge_params = {**kwargs}
			grammar = choices if self.mode == 'action' else self.grammar
			if isinstance(grammar, str):
				grammar = {'type': 'object', 'properties': {'state': {'type': 'string', 'pattern': grammar}}}
			if grammar is not None:
				judge_params['grammar'] = grammar
			if self.judge_chat:
				# If judge_chat is True, we assume the judge will handle the chat directly
				chat.append({'role': 'user', 'content': judge_prompt})
				self.judge.step(chat, **judge_params)
				verdict = chat[-1]['content']
			else:
				verdict = self.judge.get_response(judge_prompt, **judge_params)

			if isinstance(grammar, dict):
				verdict = json.loads(verdict)
				verdict = next(iter(verdict.values()))

			log.append({"sender": "Judge", "type": "extracting", "content": verdict})

		return verdict


# class ActionPlayer(SimplePlayer):
# 	@property
# 	def ident(self):
# 		return f'action'
#
# 	def next_state(self, client: AbstractClient, game: GameBase, state: JSONDATA, log: list[dict[str, str]],
# 				   judge: Optional[AbstractClient] = None):
# 		outcome = super().next_state(client, game, state, log, judge=judge)
# 		new_state = game.decode_state(outcome, state)
# 		return new_state
#
# 		action = self.extract_action(chat, game, observation, choices, log)
# 		log.append({"sender": "Judge", "type": "judge", "content": f'Action: {action}'})
# 		new_state = game.update_state(state, game.decode_action(action, state, actions),
# 									  allow_violations=True)
# 		self.client = None
# 		self.judge = None
# 		return new_state
#
# 	def extract_action(self, chat: List[Dict[str, str]], game: GameBase, obs: JSONDATA, choices: List[JSONDATA],
# 					   log: List[Dict[str, str]]) -> JSONDATA:
# 		raise NotImplementedError



# @fig.component('ttt/action')
# class TTT_Action(ActionPlayer):
# 	def __init__(self, params: JSONOBJ = {}, template: str = 'game/ttt/action/act',
# 				 judge_template: str = 'game/ttt/judge', judge_continue = False, **kwargs):
# 		super().__init__(params=params, template=template, judge_template=judge_template,
# 						 judge_continue=judge_continue, **kwargs)
# 		self._state_regex = r'^[XO_]{9}$'
#
# 	def _extract_decision(self, response: str, state: JSONDATA, actions: List[JSONDATA]) -> JSONDATA:
# 		if self.mode == 'actions':
# 			return self._find_last(r'\b(\d+)\b', response)
# 		raise NotImplementedError
#
# 	def _judge_grammar(self, state, actions: List[int]) -> str:
#
# 		return [str(a) for a in actions] if self.mode == 'actions'
#
# 	def encode_state(self, state: JSONDATA) -> str:
# 		options = []
# 		index = 1
# 		for v in state['board']:
# 			if v == '_':
# 				options.append(str(index))
# 				index += 1
# 			else:
# 				options.append(v)
# 		# options = [v if v != '_' else i+1 for i, v in enumerate(state['board'])]
# 		nested = [options[i:i + 3] for i in range(0, 9, 3)]
# 		state_str = tabulate(nested, tablefmt='grid', stralign='center')
# 		return state_str
#
# 	def decode_state(self, state_str: str) -> JSONDATA:
# 		return {'board': state_str, 'player_to_move': 'X'}
#
# 	def validate_action(self, action: str, actions: List[int]) -> int:
# 		return actions[int(action.strip()) - 1]


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

			# apikey = data.get('key')
			# if apikey != 'retreat':
			# 	return jsonify({'error': 'Invalid API key'}), 403

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




