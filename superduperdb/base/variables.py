import dataclasses as dc
import importlib
import inspect
import typing as t

from pinnacledb.base.leaf import Leaf


def _from_dict(r: t.Any, db: None = None) -> t.Any:
    from pinnacledb.base.document import Document
    from pinnacledb.components.datatype import LazyArtifact, LazyFile

    if isinstance(r, Document):
        r = r.unpack(db, leaves_to_keep=(LazyArtifact, LazyFile))
    if isinstance(r, (list, tuple)):
        return [_from_dict(i, db=db) for i in r]
    if not isinstance(r, dict):
        return r
    if '_content' in r:
        r = r['_content']
    if 'cls' in r and 'module' in r and 'dict' in r:
        module = importlib.import_module(r['module'])
        cls_ = getattr(module, r['cls'])
        if inspect.isfunction(cls_):
            return cls_(**r['dict'])
        kwargs = _from_dict(r['dict'], db=db)
        kwargs_init = {k: v for k, v in kwargs.items() if k not in cls_.set_post_init}
        kwargs_post_init = {k: v for k, v in kwargs.items() if k in cls_.set_post_init}
        instance = cls_(**kwargs_init)
        for k, v in kwargs_post_init.items():
            setattr(instance, k, v)
        return instance
    else:
        return {k: _from_dict(v, db=db) for k, v in r.items()}


class VariableError(Exception):
    """Variable error."""

    ...


def _find_variables(r):
    if isinstance(r, dict):
        return sum([_find_variables(v) for v in r.values()], [])
    if isinstance(r, (list, tuple)):
        return sum([_find_variables(v) for v in r], [])
    if isinstance(r, Variable):
        return [r]
    if isinstance(r, Leaf):
        return r.variables
    return []


def _find_variables_with_path(r):
    if isinstance(r, dict):
        out = []
        for k, v in r.items():
            tmp = _find_variables_with_path(v)
            for p in tmp:
                out.append({'path': [k] + p['path'], 'variable': p['variable']})
        return out
    elif isinstance(r, (list, tuple)):
        out = []
        for i, v in enumerate(r):
            tmp = _find_variables_with_path(v)
            for p in tmp:
                out.append({'path': [i] + p['path'], 'variable': p['variable']})
        return out
    elif isinstance(r, Variable):
        return [{'path': [], 'variable': r}]
    return []


def _replace_variables(x, db, **kwargs):
    from .document import Document

    if isinstance(x, dict):
        return {
            _replace_variables(k, db, **kwargs): _replace_variables(v, db, **kwargs)
            for k, v in x.items()
        }
    if isinstance(x, (list, tuple)):
        return [_replace_variables(v, db, **kwargs) for v in x]
    if isinstance(x, Variable):
        return x.set(db, **kwargs)
    if isinstance(x, Document):
        return x.set_variables(db, **kwargs)
    return x


@dc.dataclass(kw_only=True)
class Variable(Leaf):
    """
    Mechanism for allowing "free variables" in a leaf object.
    The idea is to allow a variable to be set at runtime, rather than
    at object creation time.

    :param value: The name of the variable to be set at runtime.
    :param setter_callback: A callback function that takes the value, datalayer
                            and kwargs as input and returns the formatted
                            variable.
    """

    value: t.Any
    setter_callback: dc.InitVar[t.Optional[t.Callable]] = None

    def __post_init__(self, db, artifacts):
        super().__post_init__(db)

    def __repr__(self) -> str:
        return '$' + str(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def set(self, db, **kwargs):
        """
        Get the intended value from the values of the global variables.

        :param db: The datalayer instance.
        :param **kwargs: Variables to be used in the setter_callback
                       or as formatting variables.

        >>> Variable('number').set(db, number=1.5, other='test')
        1.5

        """
        if self.setter_callback is not None:
            try:
                return self.setter_callback(db, self.value, kwargs)
            except Exception as e:
                raise VariableError(
                    f'Could not set variable {self.value} '
                    f'based on {self.setter_callback} and **kwargs: {kwargs}'
                ) from e
        else:
            assert isinstance(self.value, str)
            return kwargs[self.value]
