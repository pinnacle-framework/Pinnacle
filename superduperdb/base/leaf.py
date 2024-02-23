import typing as t
from abc import ABC, abstractmethod, abstractproperty

from pinnacledb.base.config import BytesEncoding

_CLASS_REGISTRY = {}


class Leaf(ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._register_class()

    @classmethod
    def _register_class(cls):
        """
        Register class in the class registry and set the full import path
        """
        full_import_path = f"{cls.__module__}.{cls.__name__}"
        cls.full_import_path = full_import_path
        _CLASS_REGISTRY[full_import_path] = cls

    @abstractproperty
    def unique_id(self):
        pass

    def unpack(self, db=None):
        return self

    @abstractmethod
    def encode(
        self,
        bytes_encoding: t.Optional[BytesEncoding] = None,
        leaf_types_to_keep: t.Sequence = (),
    ):
        pass

    @classmethod
    @abstractmethod
    def decode(cls, r, db, reference: bool = False):
        pass

    def init(self, db=None):
        pass


def find_leaf_cls(full_import_path) -> t.Type[Leaf]:
    """Find leaf class by class full import path"""
    return _CLASS_REGISTRY[full_import_path]
