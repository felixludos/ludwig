# Project Ludwig

## Defining Settings

| Task                   | Type         | Priority | Sources | Design Tasks | Implemenet Tasks | Completed |
|------------------------|--------------|----------|---------|--------------|------------------|-----------|
| Synthetic Languages    | synthetic    | **       |         |              |                  |           |
| Tic-tac-toe            | closed (toy) | **       | N/A     | X            |                  |           |
| Chess                  | closed       | ***      | X       | X            |                  |           |
| Equation-solving       | closed       | *        |         |              |                  |           |
| Geometry formalization | semi-closed  | *        |         |              |                  |           |
| Causal Modeling        | semi-closed  | **       |         |              |                  |           |
| Legal                  | open         | ***      | X       |              |                  |           |
| Stocks/Finances        | open         | *        |         |              |                  |           |


See the [Task and Tool Definitions](ludwig/core/base.py) for the expected APIs for defining settings. I suggest you subclass those classes as seen in the [Tic-tac-toe](ludwig/tictactoe/example.py) example. For now, prioritize the `generate` and `observe` methods (as well as the relevant system and task context) over side information and any formatting/parsing that may be involved in `score` or `correct`. Especially if you can formulate the task in terms of a multiple choice or yes/no question, then evaluation will be quite straightforward.

Each setting should define multiple individual tasks (which generally share system contexts, but don't necessarily have to). If you need access to larger datafiles or other resources for specific tasks, ideally have a minimal demo version of the datafiles in `assets/` for testing purposes, but we'll coordinate on that later.

Common utilities, such as extracting/parsing/validating python code in an LLM response or querying LLMs for structured outputs (e.g. based on a given JSON schema) will be available soon.



