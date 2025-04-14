from .example import TakeTheMiddle


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


