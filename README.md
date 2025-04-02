# Project Ludwig

## Installation

Generally, you should be able to install all dependencies using the following command:

```bash
pip install -r requirements.txt
```

But check the [requirements.txt](requirements.txt) as we will likely add more dependencies as we go along.

To run the existing unit tests, and thereby validate that the setup was successful, you can run the following command:

```bash
pytest
```

## Demo

When running `python main.py -h` (or equivalently `fig -h`) you should see a list of available commands.

Also, to run a simple minimal demo of the `eval` script, you can run the following command:

```bash
python main.py eval demo
```


## Defining Settings

| Task                   | Type         | Priority | Sources | Design Tasks | Implement Tasks | Completed |
|------------------------|--------------|----------|---------|--------------|-----------------|-----------|
| Synthetic Languages    | synthetic    | **       |         |              |                 |           |
| Tic-tac-toe            | closed (toy) | **       | N/A     | X            |                 |           |
| Chess                  | closed       | ***      | X       | X            |                 |           |
| Equation-solving       | closed       | *        |         |              |                 |           |
| Geometry formalization | semi-closed  | *        |         |              |                 |           |
| Causal Modeling        | semi-closed  | **       |         |              |                 |           |
| Legal                  | open         | ***      | X       |              |                 |           |
| Stocks/Finances        | open         | *        |         |              |                 |           |


See the [Task and Tool Definitions](ludwig/abstract.py) for the expected APIs for defining settings. I suggest you subclass those classes as seen in the [Tic-tac-toe](ludwig/tictactoe/example.py) example. For now, prioritize the `generate` and `observe` methods (as well as the relevant system and task context) over side information and any formatting/parsing that may be involved in `score` or `correct`. Especially if you can formulate the task in terms of a multiple choice or yes/no question, then evaluation will be quite straightforward.

Each setting should define multiple individual tasks (which generally share system contexts, but don't necessarily have to). If you need access to larger datafiles or other resources for specific tasks, ideally have a minimal demo version of the datafiles in `assets/` for testing purposes, but we'll coordinate on that later.

Common utilities, such as extracting/parsing/validating python code in an LLM response or querying LLMs for structured outputs (e.g. based on a given JSON schema) will be available soon.

### Chess
Read it here - [readme.md](ludwig/chess/readme.md)

Download the full dataset - [lichess db](https://drive.google.com/file/d/1140o8aqMb2dOT2D9P7SoCSPmiXpLA9Sd/view?usp=sharing)


## Define Subjects

Subjects are any decision-making system that can solve tasks. See `AbstractSubject` in [abstract.py](ludwig/abstract.py) for the expected API. And [`DirectPrompting`](ludwig/baselines/simple.py) for a simple example of a subject that should directly prompt an LLM with a fixed pre-defined prompt template.

