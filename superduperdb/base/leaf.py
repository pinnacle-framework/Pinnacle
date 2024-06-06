import dataclasses as dc
import importlib
import inspect
import typing as t
import uuid

from pinnacledb.misc.annotations import extract_parameters, replace_parameters
from pinnacledb.misc.serialization import asdict
from pinnacledb.misc.special_dicts import SuperDuperFlatEncode

_CLASS_REGISTRY = {}

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer
    from pinnacledb.components.schema import Schema


def _import_item(
    dict,
    cls: t.Optional[str] = None,
    module: t.Optional[str] = None,
    object: t.Optional[type] = None,
    db: t.Optional['Datalayer'] = None,
):
    if object is None:
        assert cls is not None
        assert module is not None
        module = importlib.import_module(module)
        object = getattr(module, cls)

    try:
        return object(**dict, db=db)
    except TypeError as e:
        if 'got an unexpected keyword argument' in str(e):
            if callable(object) and not inspect.isclass(object):
                return object(
                    **{
                        k: v
                        for k, v in dict.items()
                        if k in inspect.signature(object).parameters
                    },
                    db=db,
                )
            init_params = {
                k: v
                for k, v in dict.items()
                if k in inspect.signature(object.__init__).parameters
            }
            post_init_params = {
                k: v for k, v in dict.items() if k in object.set_post_init
            }
            instance = object(**init_params, db=db)
            for k, v in post_init_params.items():
                setattr(instance, k, v)
            return instance
        raise e


class LeafMeta(type):
    """Metaclass that pinnacles docstrings # noqa."""

    def __new__(mcs, name, bases, namespace):
        """Create a new class with pinnacled docstrings # noqa."""
        # Prepare namespace by extracting annotations and handling fields
        annotations = namespace.get('__annotations__', {})
        for k, v in list(namespace.items()):
            if isinstance(v, (type, dc.InitVar)):
                annotations[k] = v
            if isinstance(v, dc.Field):
                annotations[
                    k
                ] = v.type  # Ensure field types are recorded in annotations

        # Update namespace with proper annotations
        namespace['__annotations__'] = annotations

        # Determine if any bases are dataclasses and
        # apply the appropriate dataclass decorator
        if bases and any(dc.is_dataclass(b) for b in bases):
            # Derived classes: kw_only=True
            cls = dc.dataclass(kw_only=True, repr=not name.endswith('Query'))(
                super().__new__(mcs, name, bases, namespace)
            )
        else:
            # Base class: kw_only=False
            cls = dc.dataclass(kw_only=False)(
                super().__new__(mcs, name, bases, namespace)
            )

        # Merge docstrings from parent classes
        parent_doc = next(
            (parent.__doc__ for parent in inspect.getmro(cls)[1:] if parent.__doc__),
            None,
        )
        if parent_doc:
            parent_params = extract_parameters(parent_doc)
            child_doc = cls.__doc__ or ''
            child_params = extract_parameters(child_doc)
            for k in child_params:
                parent_params[k] = child_params[k]
            placeholder_doc = replace_parameters(child_doc)
            param_string = ''
            for k, v in parent_params.items():
                v = '\n    '.join(v)
                param_string += f':param {k}: {v}\n'
            cls.__doc__ = placeholder_doc.replace('!!!', param_string)
        return cls


class Leaf(metaclass=LeafMeta):
    """Base class for all leaf classes.

    :param identifier: Identifier of the leaf.
    :param db: Datalayer instance.
    :param uuid: UUID of the leaf.
    """

    set_post_init: t.ClassVar[t.Sequence[str]] = ()

    identifier: str
    db: dc.InitVar[t.Optional['Datalayer']] = None
    uuid: str = dc.field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self, db):
        self.db: 'Datalayer' = db

    @property
    def leaves(self):
        """Get all leaves in the object."""
        return {
            f.name: getattr(self, f.name)
            for f in dc.fields(self)
            if isinstance(getattr(self, f.name), Leaf)
        }

    @property
    def _id(self):
        return f'{self.__class__.__name__.lower()}/{self.uuid}'

    def encode(self, schema: t.Optional['Schema'] = None, leaves_to_keep=()):
        """Encode itself.

        After encoding everything is a vanilla dictionary (JSON + bytes).

        :param schema: Schema instance.
        :param leaves_to_keep: Leaves to keep.
        """
        cache: t.Dict[str, dict] = {}
        blobs: t.Dict[str, bytes] = {}
        files: t.Dict[str, str] = {}

        self._deep_flat_encode(cache, blobs, files, leaves_to_keep, schema)
        return SuperDuperFlatEncode(
            {
                '_base': f'?{self._id}',
                '_leaves': cache,
                '_blobs': blobs,
                '_files': files,
            }
        )

    def set_variables(self, **kwargs) -> 'Leaf':
        """Set free variables of self.

        :param db: Datalayer instance.
        :param kwargs: Keyword arguments to pass to `_replace_variables`.
        """
        from pinnacledb import Document
        from pinnacledb.base.variables import Variable, _replace_variables

        r = self.dict().encode(leaves_to_keep=(Variable,))
        r = _replace_variables(r, **kwargs)
        return Document.decode(r).unpack()

    @property
    def variables(self) -> t.List[str]:
        """Get list of variables in the object."""
        from pinnacledb.base.variables import Variable, _find_variables

        return list(set(_find_variables(self.encode(leaves_to_keep=Variable))))

    def _deep_flat_encode(
        self,
        cache,
        blobs,
        files,
        leaves_to_keep=(),
        schema: t.Optional['Schema'] = None,
    ):
        if isinstance(self, leaves_to_keep):
            cache[self._id] = self
            return f'?{self._id}'
        from pinnacledb.base.document import _deep_flat_encode

        r = dict(self.dict())
        # TODO change this to caches[self._id] = r etc.
        return _deep_flat_encode(
            r, cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=schema
        )

    def dict(self):
        """Return dictionary representation of the object."""
        from pinnacledb import Document

        r = asdict(self)

        from pinnacledb.components.datatype import Artifact, dill_serializer

        if self.__class__.__module__ == '__main__':
            cls = Artifact(
                x=self.__class__,
                datatype=dill_serializer,
            )
            return Document({'_object': cls, **r})
        path = (f'{self.__class__.__module__}.' f'{self.__class__.__name__}').replace(
            '.', '/'
        )
        return Document({'_path': path, **r})

    @classmethod
    def _register_class(cls):
        """Register class in the class registry and set the full import path."""
        full_import_path = f"{cls.__module__}.{cls.__name__}"
        cls.full_import_path = full_import_path
        _CLASS_REGISTRY[full_import_path] = cls

    def unpack(self):
        """Unpack object."""
        return self

    @classmethod
    def build(cls, r):
        """Build object from an encoded data.

        :param r: Encoded data.
        """
        modified = {
            k: v
            for k, v in r.items()
            if k in inspect.signature(cls.__init__).parameters
        }
        return cls(**modified)

    def init(self, db=None):
        """Initialize object.

        :param db: Datalayer instance.
        """
        pass


def find_leaf_cls(full_import_path) -> t.Type[Leaf]:
    """Find leaf class by class full import path.

    :param full_import_path: Full import path of the class.
    """
    return _CLASS_REGISTRY[full_import_path]
