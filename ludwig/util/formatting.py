from .imports import *

from ..jsonutils import flatten, deep_get, deep_remove

try:
    from omnibelt import wrap_text
except ImportError:
    # print(f'WARNING: omnibelt is out of date')
    def wrap_text(data: str, width: int = 80) -> str:
        """
        Format data for display.
        """
        return '\n'.join(textwrap.wrap(str(data), width=width))







