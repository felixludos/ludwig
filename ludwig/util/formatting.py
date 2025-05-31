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


class SimpleFormatter(AbstractFormatter):
    def extract(self, data: JSONOBJ, key: str, *, sep: str = '.') -> Any:
        """
        Extract a value from data for the given key.
        """
        return deep_get(data, key, sep=sep)

    def update(self, collected: JSONOBJ, key: str, value: Any) -> None:
        """
        Update the collected data with the extracted value.
        """
        collected[key] = value



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
                value = formatter.extract(raw, target, sep=self.sep) if isinstance(formatter, AbstractFormatter) \
                            else deep_get(raw, target, sep=self.sep)
            except (KeyError, ValueError):
                pass
            else:
                if isinstance(formatter, AbstractFormatter):
                    formatter.update(selected, target, value)
                elif isinstance(formatter, int):
                    self.targets[target] -= 1
                    if self.targets[target] <= 0:
                        del self.targets[target]
                        self.active.remove(target)
                else:
                    selected[target] = value


        return flatten(selected, sep=self.sep)
