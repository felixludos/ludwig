from .imports import *
from ..jsonutils import flatten, deep_get, deep_remove, AbstractJsonable

import pandas as pd
import wandb

try:
    from omnibelt import wrap_text
except ImportError:
    # print(f'WARNING: omnibelt is out of date')
    def wrap_text(data: str, width: int = 80) -> str:
        """
        Format data for display.
        """
        return '\n'.join(textwrap.wrap(str(data), width=width))


class AbstractFormatter:
    def extract(self, data: JSONOBJ, key: str, *, sep: str = '.') -> Any:
        """
        Extract a value from data for the given key.
        """
        raise NotImplementedError("Subclasses must implement extract method")

    def update(self, collected: JSONOBJ, key: str, value: Any) -> None:
        """
        Update the formatter with new data.
        """
        raise NotImplementedError("Subclasses must implement update method")


@fig.component('formatter/simple')
class SimpleFormatter(fig.Configurable, AbstractFormatter):
    def __init__(self, expires: int = None, **kwargs):
        super().__init__(**kwargs)
        self.expires = expires

    def extract(self, data: JSONOBJ, key: str, *, sep: str = '.') -> Any:
        """
        Extract a value from data for the given key.
        """
        return deep_get(data, key, sep=sep)

    def update(self, data: JSONOBJ, collected: JSONOBJ, key: str, value: Any) -> None:
        """
        Update the collected data with the extracted value.
        """
        if self.expires is None or self.expires <= 0:
            return
        self._update(data, collected, key, value)
        if self.expires is not None:
            self.expires -= 1

    def _update(self, data: JSONOBJ, collected: JSONOBJ, key: str, value: Any) -> None:
        """
        Update the collected data with the extracted value.
        """
        collected[key] = value


@fig.component('formatter/table')
class TableFormatter(SimpleFormatter):

    def _update(self, data: JSONOBJ, collected: JSONOBJ, key: str, value: Any) -> None:
        """
        Update the collected data with the extracted value.
        """
        assert isinstance(value, dict)
        tbl = {key: str(val) for key,val in flatten(value).items()}
        tbl = pd.DataFrame(tbl.items(), columns=['Key', 'Value'])
        if isinstance(tbl, pd.DataFrame):
            tbl = wandb.Table(dataframe=tbl)
        idx = data.get('idx', None)
        collected[f'{key}{idx}' if idx is not None else key] = tbl



class AbstractBroker:
    """
    Abstract base class for brokers that extract data from a jsonobj with arbitrary structure.
    """
    def extract(self, data: JSONOBJ) -> JSONFLAT:
        """
        Extract values from data for each target in targets.
        """
        raise NotImplementedError("Subclasses must implement extract method")

    def details(self) -> Iterator[Tuple[str, Optional[Any], bool]]:
        """
        Return an iterator of tuples containing target, value, and active status.
        """
        raise NotImplementedError("Subclasses must implement details method")
    
    def json(self) -> JSONOBJ:
        """
        Return a JSON representation of the broker configuration.
        """
        raise NotImplementedError("Subclasses must implement json method")
    
    def status(self) -> JSONOBJ:
        raise NotImplementedError



@fig.component('default-broker')
class DefaultBroker(fig.Configurable, AbstractBroker):
    """
    Default broker that extracts values from data for each target in targets.
    """
    def __init__(self, targets: Union[Dict[str, Any], Iterable[str]] = None, untargets: Iterable[str] = None,
                 *, sep: str = '.', **kwargs):
        if targets is None:
            targets = {}
        elif isinstance(targets, dict):
            targets = flatten(targets)
        else:
            targets = {target: True for target in targets}
        if untargets is None:
            untargets = []
        elif isinstance(untargets, dict):
            untargets = flatten(untargets)
            untargets = [untarget for untarget, active in untargets.items() if active]
        super().__init__(**kwargs)
        self.targets = targets
        self.untargets = untargets
        self.active = [target for target, active in self.targets.items() if active
                    and not any(target.startswith(untarget) for untarget in self.untargets)]
        self.sep = sep

    def _prepare_targets(self, targets: Iterable[str]) -> None:
        """
        Prepare targets for extraction.
        """
        self.targets = [target.strip() for target in targets if target.strip()]
        if not self.targets:
            raise ValueError("No valid targets provided for extraction")

    def json(self) -> JSONOBJ:
        return {
            'targets': self.targets,
            'untargets': self.untargets,
            'sep': self.sep,
        }

    def __len__(self):
        return len(self.active)

    def details(self) -> Iterator[Tuple[str, Optional[Any], bool]]:
        all_targets = [(untarget, None, False) for untarget in self.untargets]
        all_targets.extend((target, val, True) for target, val in self.targets.items() if target not in self.untargets)
        yield from all_targets

    def describe(self, title: Optional[str] = None) -> str:
        tbl = [(colorize(name, 'green' if pos else 'red'), val) for name, val, pos in self.details()]
        return tabulate(tbl, headers=['Target', 'Value'], stralign='left', numalign='left')

    def extract(self, data: JSONOBJ) -> JSONFLAT:
        raw = {}

        # extract
        for target in self.active:
            if target == '_all_':
                raw.update(flatten(data))
                break
            else:
                try:
                    value = deep_get(data, target, sep=self.sep)
                except (KeyError, ValueError):
                    pass
                else:
                    raw[target] = value

        # filter
        if self.untargets:
            raw = unflatten(raw, sep=self.sep)
            for untarget in self.untargets:
                try:
                    deep_remove(raw, untarget, sep=self.sep)
                except (KeyError, ValueError):
                    pass

        # format
        selected = {}
        for target in self.active:
            try:
                formatter = self.targets[target]
                if isinstance(formatter, AbstractFormatter):
                    value = formatter.extract(raw, target, sep=self.sep)
                elif target != '_all_':
                    value = deep_get(raw, target, sep=self.sep)
            except (KeyError, ValueError):
                pass
            else:
                if isinstance(formatter, AbstractFormatter):
                    formatter.update(data, selected, target, value)
                elif target == '_all_':
                    selected.update(raw)
                else:
                    selected[target] = value
                
                if isinstance(formatter, int) and not isinstance(formatter, bool):
                    self.targets[target] -= 1
                    if self.targets[target] <= 0:
                        del self.targets[target]
                        self.active.remove(target)


        return flatten(selected, sep=self.sep)


@fig.component('min-broker')
class MinimalBroker(DefaultBroker):
    """
    Minimal broker that extracts values from data for each target in targets.
    """
    def __init__(self, targets: Union[Dict[str, Any], Iterable[str]] = None, untargets: Iterable[str] = None,
                 *, sep: str = '.', **kwargs):
        super().__init__(targets=targets, untargets=untargets, sep=sep, **kwargs)
        self.assignments = {}
        self.displayed = {}
        self.tree = {}

    def _as_unique(self, key: str) -> str:
        if key not in self.displayed:
            return key
        i = 0
        while f'{key}{i}' in self.displayed:
            i += 1
        return f'{key}{i}'


    def _simplify_key(self, key: str):
        if key not in self.assignments:
            terms = key.split(self.sep)

            if len(terms) == 2 and terms[-1] not in self.displayed:
                self.assignments[key] = terms[-1]

            elif len(terms) > 2:
                for i in range(len(terms)):
                    addr = self.sep.join([*terms[:i], terms[-1]])
                    if addr not in self.displayed:
                        self.assignments[key] = addr
                        break

        if key not in self.assignments:
            self.assignments[key] = self._as_unique(key)

        self.displayed[self.assignments[key]] = key
        return self.assignments[key]


    def extract(self, data: JSONOBJ) -> JSONFLAT:
        """
        Extract values from data for each target in targets.
        """
        raw = super().extract(data)
        
        simple = {self._simplify_key(key): value for key, value in raw.items()}
        assert isinstance(simple, dict), f'Expected dict, got {type(simple)}'


