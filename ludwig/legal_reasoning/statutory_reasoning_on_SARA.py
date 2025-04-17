from ..imports import *
from .. import TaskBase, ToolBase, ParsingError
import pandas as pd
from typing import Optional, Tuple, List

class LegalReasoningTask(TaskBase):
    def __init__(self):
        super().__init__()
        self.statutes = None
        self.dataset = None
        self.data_len = None

    @property
    def name(self) -> str:
        return "legal-taxlaw-entailment"

    @property
    def total_questions(self) -> Optional[int]:
        return self.data_len

    def context(self) -> str:
        if self.statutes is None:
            with open('./assets/law/sara/statutes.txt', 'r') as f:
                self.statutes = f.read()
        return ("Below are relevant U.S. tax statutes:\n" + self.statutes +
                "\n\nUsing these statutes, evaluate if a given legal hypothesis logically follows from the provided premise.")

    def description(self) -> str:
        return ("Determine whether a hypothesis about U.S. tax law logically follows "
                "from a given premise using provided statutes.")

    def _load_data(self, index: int, seed: Optional[int] = None) -> Tuple[str, str, str]:
        if self.dataset is None:
            self.dataset = pd.read_csv('./assets/law/sara/train.tsv', sep='\t', header=None,
                                       names=["Premise", "Hypothesis", "Conclusion"])
            self.data_len = len(self.dataset)
        data_row = self.dataset.iloc[index % self.data_len]
        return data_row["Premise"], data_row["Hypothesis"], data_row["Conclusion"]

    def load(self, index: int, seed: Optional[int] = None) -> Tuple[List[str], str]:
        premise, hypothesis, conclusion = self._load_data(index=index, seed=seed)
        return [premise, hypothesis], conclusion

    def observe(self, problem: List[str], seed: int = None) -> str:
        return ("Premise: {}\nHypothesis: {}\n\n"
                "Based on the statutes provided, determine if the hypothesis logically follows from the premise. "
                "Answer 'Entailment', 'Contradiction', or provide a numeric value if required.").format(*problem)

    def correct(self, response: str, answer: str) -> bool:
        response = response.strip().lower().replace('$', '').replace(',', '')
        answer = answer.strip().lower().replace('$', '').replace(',', '')

        if answer in ["entailment", "contradiction"]:
            return response == answer
        else:
            try:
                return float(response) == float(answer)
            except ValueError:
                return False

    def validation(self, N: int, seed: Optional[int] = None) -> List[Tuple[str, str]]:
        return [self.load(i, seed=seed) for i in range(N)]

    def rationale(self, problem: List[str], answer: str, seed: Optional[int] = None) -> List[str]:
        return ["Review statutes", "Identify relevant rules", "Check if conditions match premise",
                "Evaluate hypothesis", f"Conclude {answer}"]

    def explanation(self, problem: List[str], answer: str, seed: Optional[int] = None) -> str:
        return ("Using the statutes, we first confirm facts provided by the premise. Then, we check each "
                "condition required by the hypothesis. If all conditions match the statutes and premise, "
                f"the result is '{answer}'.")


if __name__ == '__main__':
	legal_puzzles = LegalReasoningTask()
	[premise, hypothesis], conclusion = legal_puzzles.load(index=10)
	print(premise + '\n' + hypothesis + '\n' + str(conclusion))
