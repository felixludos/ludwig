from .imports import *


class ToolUse(ClientStrategy):
    """
    Tool use strategy.
    """

    def __init__(self, template: Union[PromptTemplate, str] = '{task_context}\n\n{question}', **kwargs):
        if not isinstance(template, PromptTemplate):
            template = PromptTemplate(template)
        super().__init__(**kwargs)
        self.template = template
        self.system_context = None
        self.task_context = None



