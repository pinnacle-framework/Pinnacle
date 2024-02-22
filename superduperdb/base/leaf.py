import typing as t
from abc import ABC, abstractmethod, abstractproperty

from pinnacledb.base.config import BytesEncoding


class Leaf(ABC):
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
    def decode(cls, r, db):
        pass

    def init(self, db=None):
        pass
