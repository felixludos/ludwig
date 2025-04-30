import json
from .example import TakeTheMiddle, StateValue, NextMove, ToolError


def test_example_task():
	from ..evaluation.judging import FinalAnswerJudge

	task = TakeTheMiddle()
	judge = FinalAnswerJudge()

	judge.prepare(task.specification())

	x, y = task.load(0)

	prompt = task.observe(x)
	print()
	print(prompt)

	response = 'final answer: no'
	assert judge.judge(response, 'no')[0] == True

	response = 'final answer: yes'
	assert judge.judge(response, 'no')[0] == False


def test_value_tool():

	tool = StateValue(rep_type='nested', val_type='minimax')

	state = [['X', 'X', 'O'],
			 ['O', 'X', 'O'],
			 [' ', ' ', ' ']]

	value = tool.call({'state': state})
	assert value == 1, f'Expected 1, got {value}'

	state = [['X', 'X', 'O'],
			 ['O', 'X', 'O'],
			 [' ', ' ', 'X']]

	value = tool.call({'state': state})
	assert value == 1, f'Expected 1, got {value}'

	state = [['X', 'X', 'O'],
			 ['O', 'X', 'O'],
			 ['X', ' ', ' ']]
	value = tool.call({'state': state})
	assert value == -1, f'Expected -1, got {value}'

	state = [['X', 'X', 'O'],
			 ['O', 'X', 'O'],
			 ['X', ' ', 'O']]
	value = tool.call({'state': state})
	assert value == -1, f'Expected -1, got {value}'

	tool = StateValue(rep_type='str', val_type='expectimax')
	state = ' '*9
	value = tool.call({'state': state})
	assert 0 < value < 1, f'Expected 0 < {value} < 1, got {value}'

	state = 'X'*9
	try:
		value = tool.call({'state': state})
	except ToolError as e:
		assert str(e) == 'Invalid or impossible state: XXXXXXXXX', f'Expected error, got {e}'
	else:
		assert False, 'Expected error, got no error'

	tool = StateValue(rep_type='list', val_type='minimax')

	state = ['X', 'X', 'O', ' ', 'X', 'O', ' ', ' ']
	try:
		value = tool.call({'state': state})
	except ToolError as e:
		assert str(e) == 'State must be a list of length 9.', f'Expected error, got {e}'
	else:
		assert False, 'Expected error, got no error'

	state.append('')
	try:
		value = tool.call({'state': state})
	except ToolError as e:
		assert str(e) == "State can only contain 'X', 'O', or ' '.", f'Expected error, got {e}'
	else:
		assert False, 'Expected error, got no error'

	tool = NextMove(rep_type='str')

	state = ' '*9
	next_states = json.loads(tool.call({'state': state}))
	assert len(next_states) == 9, f'Expected 9 next states, got {len(next_states)}'






