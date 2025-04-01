import re
from ..imports import *
from ..core import ParsingError
from .make_next_move import MakeNextMove


class MakeBestMove(MakeNextMove):
    def __init__(self):
        super().__init__()

    def load(self, index: int, *, seed: Optional[int] = None) -> Tuple[List[str], str]:
        board_state, next_best_moves = self._load_data(index=index, seed=seed)
        return [board_state, ], next_best_moves.strip().split(' ')[0]

    def correct(self, response: str, answer: bool) -> bool:
        # in this case the answer must be all possible  moves
        clean = response.strip().lower()
        uci_regex = re.compile(r'^[a-h][1-8][a-h][1-8][nbrqNBRQ]?$')
        castling_regex = re.compile(r'^O-O(-O)?$')
        # TODO(Partha, Felix): opportunity here return better error messages.
        if bool(uci_regex.match(clean)) or bool(castling_regex.match(clean)):
            if clean == answer:
                return True
            else:
                ParsingError(response, 'Returned answer a valid move but not the best one.')
        raise ParsingError(response, 'Returned answer is not a valid chess move. It must follow UCI notation')

    def observe(self, problem: List[str], *, seed: int = None) -> str:
        # This is a placeholder implementation for demo purposes.
        template = ("Here is a chess board state in 'fen' format {0}. Please answer with the next best move in UCI "
                    "notation. Be careful to check which side is to move")
        return template.format(*problem)