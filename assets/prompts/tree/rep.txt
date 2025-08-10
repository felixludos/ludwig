We will solve the following task using a structured tree-search framework.

**Task Description:**
{task}

**Example Problem:**
```
{examples[0]['question']}
```

Your first task is to design an optimal state representation for this kind of problem. The representation must be:
1.  **High-Fidelity:** It must capture all details necessary to solve the task unambiguously.
2.  **Efficient:** It should contain minimal redundancy and exclude irrelevant "nuisance" details.
3.  **Conducive to Search:** The structure should make it easy to implement the search functions (`expand`, `extract`, `evaluate`) which are crucial for the tree search algorithm.

Define this representation as a JSON schema, including clear descriptions for each property. Enclose the final output in a ```json ... ``` block.