from .imports import *



def flatten(d, parent_key='', sep='.'):
    items = {}
    for k, v in d.items() if isinstance(d, dict) else enumerate(d):
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, (dict, list)) and not isinstance(v, str):
            items.update(flatten(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


