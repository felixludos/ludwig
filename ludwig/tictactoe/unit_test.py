from .example import TakeTheMiddle



def test_example_task():

	task = TakeTheMiddle()

	x, y = task.load(0)

	prompt = task.observe(x)
	print()
	print(prompt)

	response = 'no'
	assert task.correct(response, y) == True

	response = 'yes'
	assert task.correct(response, y) == False


