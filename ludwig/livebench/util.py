
from typing import Optional, Callable
import itertools
import re


def get_result_interpreter(subtask: str, release_date: str) -> Callable[[str, str, bool], float]:
	if subtask == 'zebra_puzzle':
		return get_zebra_puzzle_evaluator(release_date)
	elif subtask == 'spatial':
		return spatial_process_results
	elif subtask == 'web_of_lies_v2':
		return web_of_lies_process_results
	else:
		raise NotImplementedError(f'No result interpreter for subtask {subtask}')


# Taken from https://github.com/LiveBench/LiveBench/

def web_of_lies_process_results(ground_truth: str, llm_answer: str, debug=False) -> int:
	score = 0
	parsed_answer = None

	# extract text from <solution></solution> tags
	solution_matches = re.findall(r'<solution>(.*?)</solution>', llm_answer)

	if len(solution_matches) == 0:
		solution_matches = re.findall(r'</solution>(.*?)</solution>', llm_answer)

	if len(solution_matches) > 0:
		parsed_answer = solution_matches[-1]

	# pull out words in bold
	bold_words = re.findall(r'\*\*(.*?)\*\*', llm_answer)

	if parsed_answer is None and bold_words:
		bold_words = [word.lower().strip().replace(',', '').replace('.', '')[0:max(len(word), 3)] for match in
					  bold_words for word in match.split()]
		parsed_answer = []
		i = len(bold_words) - 1
		while i >= 0 and len(parsed_answer) < 3:
			if bold_words[i] in ["yes", "no", "unknown"]:
				parsed_answer = [bold_words[i]] + parsed_answer
			i -= 1
		if len(parsed_answer) > 0:
			parsed_answer = ", ".join(parsed_answer)
		else:
			parsed_answer = None

	allow_latex = True
	if parsed_answer is None or parsed_answer.strip() == '' and allow_latex:
		llm_answer = llm_answer.replace("\\\\boxed{\\\\textbf{", "\\\\boxed{")
		llm_answer = llm_answer.replace("\\\\fbox{", "\\\\boxed{")
		llm_answer = llm_answer.replace("\\textbf{", "\\boxed{")

		last_boxed = last_boxed_only_string(llm_answer)
		if last_boxed:
			parsed_answer = remove_boxed(last_boxed)

	allow_plain = True
	if allow_plain and parsed_answer is None:
		combs = itertools.product(['yes', 'no', 'unknown'], repeat=3)
		# find all instances of these combinations in the answer, then treat the last one as the actual answer
		# to compare to the ground truth
		final_comb = None
		final_comb_index = -1
		for comb in combs:
			index = llm_answer.lower().find(', '.join(comb))
			if index != -1 and index > final_comb_index:
				final_comb = comb
				final_comb_index = index
		if final_comb is not None:
			parsed_answer = ', '.join(final_comb)

	# Check if parsed_answer is an exact match of ground_truth
	if parsed_answer and parsed_answer == ground_truth.lower():
		score = 1

	# Check if parsed_answer contains the ground_truth
	if parsed_answer and parsed_answer.count("yes") + parsed_answer.count("no") + parsed_answer.count(
			"unknown") == 3 and ground_truth.lower() in parsed_answer:
		score = 1

	if debug and score == 0:
		print("INCORRECT")
		print('GROUND TRUTH', ground_truth)
		if parsed_answer:
			print('PARSED ANSWER', parsed_answer)
		else:
			print('NO PARSED ANSWER')
		print('END OF OUTPUT', llm_answer[-50:])

	return score

def spatial_process_results(ground_truth: str, llm_answer: str, debug=False) -> int:

    if llm_answer == ground_truth:
        return 1

    word_to_number = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14', 'fifteen': '15',
        'sixteen': '16', 'seventeen': '17', 'eighteen': '18', 'nineteen': '19', 'twenty': '20'
    }

    bold_words = re.findall(r'\*\*([^\*]+)\*\*', llm_answer)
    score = 0

    # allow the answer to be within the last 3 bolded words
    words_to_check = []
    for i in range(3):
        if bold_words and len(bold_words) > i:
            words_to_check.append(bold_words[-i-1].strip().lower())

    for i, word in enumerate(words_to_check):
        if word == ground_truth.strip().lower():
            score = 1

        # allow the answer to be the number spelled out
        if word in word_to_number and word_to_number[word] == ground_truth.strip().lower():
            score = 1

        # allow certain cases like "two tetrahedra" == "tetrahedra" and "equilateral triangle" == "triangle"
        # while still disallowing cases like "circle square triangle" == "triangle"
        for answer in ["tetrahedra", "tetrahedron", "triangle", "square"]:
            if ground_truth.strip().lower() == answer and answer in word and len(word) < (2 * len(answer) + 5):
                score = 1

    allow_boxed = True
    if score == 0 and allow_boxed:
        llm_answer = llm_answer.replace("\\\\fbox{", "\\\\boxed{")
        last_boxed = last_boxed_only_string(llm_answer)
        if last_boxed:
            parsed_answer = remove_boxed(last_boxed)
            parsed_answer = parsed_answer.replace("\\textbf{", "")
            parsed_answer = parsed_answer.replace("\\mathbf{", "")
            parsed_answer = parsed_answer.replace("\\text{", "")
            parsed_answer = parsed_answer.replace("}", "")
            if parsed_answer == ground_truth:
                score = 1

    if debug and score == 0:
        print("INCORRECT")
        print("GROUND TRUTH", ground_truth.strip().lower())
        if bold_words:
            print("BOLD WORDS:", bold_words[-1].strip().lower())
        if last_boxed:
            print("LAST BOXED", last_boxed)
            print("PARSED ANSWER", parsed_answer)
        print("END OF OUTPUT", llm_answer[-50:])

    return score

def get_zebra_puzzle_evaluator(release_date: str):
    if release_date < '2024-11-25':
        return zebra_puzzle_process_results_old
    return zebra_puzzle_process_results

def zebra_puzzle_process_results(ground_truth: str, llm_answer: str, debug=False) -> float:
	# Mapping of numbers to words for 1 to 9
	word_to_num = {
		'one': '1',
		'two': '2',
		'three': '3',
		'four': '4',
		'five': '5',
		'six': '6',
		'seven': '7',
		'eight': '8',
		'nine': '9'
	}

	ground_truth = ground_truth.split(',')

	# extract text from <solution></solution> tags
	solution_matches = re.findall(r'<solution>(.*?)</solution>', llm_answer)

	if len(solution_matches) == 0:
		solution_matches = re.findall(r'</solution>(.*?)</solution>', llm_answer)


	allow_boxed = True
	if len(solution_matches) == 0 and allow_boxed:
		llm_answer = llm_answer.replace("\\\\fbox{", "\\\\boxed{")
		last_boxed = last_boxed_only_string(llm_answer)
		if last_boxed:
			boxed_removed = remove_boxed(last_boxed)
			boxed_removed = boxed_removed.replace("\\text{", "").replace("}", "").replace('\\', '')
			solution_matches.append(boxed_removed)

	if len(solution_matches) == 0:
		last_line = llm_answer.strip().split('\n')[-1]
		if last_line.count(',') == len(ground_truth) - 1:
			solution_matches.append(last_line)


	if len(solution_matches) == 0:
		if debug:
			print('No solution text found for zebra puzzle')
			print('GROUND TRUTH', ground_truth)
			print('END OF OUTPUT', llm_answer[-100:])
		return 0

	if len(solution_matches) > 1:
		if debug:
			print('WARNING: Multiple solution texts found for zebra puzzle, combining starting from last')
		all_solution_text = []
		for match in solution_matches:
			all_solution_text += match.split(',')
		# get last len(ground_truth) elements
		solution_text = all_solution_text[-len(ground_truth):]
	else:
		solution_text = solution_matches[-1].split(',')

	if debug and len(solution_text) < len(ground_truth):
		print \
			(f'WARNING: LLM does not have an answer for all zebra puzzle questions (expected {len(ground_truth)}, got {len(solution_text)})')

	num_correct = 0
	total = len(ground_truth)
	for i in range(total):
		gt_word = ground_truth[i].strip().lower().replace('-', ' ')
		if i >= len(solution_text):
			continue
		llm_word = solution_text[i].strip().lower().replace('-', ' ').replace('position', '')
		if llm_word in word_to_num:
			# llm_word = word_to_num[llm_word]
			if debug:
				print('WARNING: LLM answer contains numbers in word form')

		if i < len(solution_text) and (gt_word == llm_word or gt_word in llm_word):
			num_correct += 1
	if debug and num_correct < total:
		print('INCORRECT', num_correct / total)
		print('GROUND TRUTH', ground_truth)
		print('SOLUTION', solution_text)
		print('END OF OUTPUT', llm_answer[-50:])
	return ((num_correct == total) + num_correct / total) / 2


def zebra_puzzle_process_results_old(ground_truth: str, llm_answer: str, debug=False) -> int:
	# Mapping of numbers to words for 1 to 9
	number_to_word = {
		'1': 'one', '2': 'two', '3': 'three', '4': 'four',
		'5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
	}

	# Pull out words in bold
	bold_words = re.findall(r'\*\*\*(\w+)\*\*\*', llm_answer)

	score = 0

	# Remove any trailing punctuation from the last bold word if exists
	if bold_words:
		if (bold_words[-1].lower() == ground_truth.lower() or
				(bold_words[-1] in number_to_word and number_to_word[bold_words[-1]].lower() == ground_truth.lower())
				or bold_words[-1].lower() + ' movies' == ground_truth.lower()):
			score = 1
	else:
		# Split the text into words and remove punctuation.
		words = re.findall(r'\b\w+\b', llm_answer)
		last_word = words[-1] if words else ''
		# Check if the last bold word is a number and matches the word representation of the ground_truth
		if (last_word.lower() == ground_truth.lower() or
				(last_word in number_to_word and number_to_word[last_word].lower() == ground_truth.lower())
				or last_word.lower() + ' movies' == ground_truth.lower()):
			score = 1

	if debug and score == 0:
		print('INCORRECT')
		print('GROUND TRUTH', ground_truth.lower())
		if bold_words:
			print('LAST BOLD WORD', bold_words[-1].lower())
		else:
			print('LAST WORD', last_word.lower())
		print('END OF OUTPUT', llm_answer[-50:])
	return score


def last_boxed_only_string(string: str) -> Optional[str]:
	idx = string.rfind("\\boxed")

	if "\\boxed " in string:
		return "\\boxed " + string.split("\\boxed ")[-1].split("$")[0]
	if idx < 0:
		idx = string.rfind("\\fbox")
		if idx < 0:
			return None

	i = idx
	right_brace_idx = None
	num_left_braces_open = 0
	while i < len(string):
		if string[i] == "{":
			num_left_braces_open += 1
		if string[i] == "}":
			num_left_braces_open -= 1
			if num_left_braces_open == 0:
				right_brace_idx = i
				break
		i += 1

	if right_brace_idx is None:
		retval = None
	else:
		retval = string[idx : right_brace_idx + 1].replace("$", "").replace("fbox","boxed")

	return retval


def remove_boxed(s: str) -> str:
	if "\\boxed " in s:
		left = "\\boxed "
		assert s[: len(left)] == left
		return s[len(left) :]

	left = "\\boxed{"

	assert s[: len(left)] == left
	assert s[-1] == "}"

	return s[len(left) : -1]





