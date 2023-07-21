from abc import ABC, abstractmethod
import typing as t

from pinnacledb.core.model import Model
from pinnacledb.core.document import Document
from pinnacledb.datalayer.base.query import Select


class BaseDataBackend(ABC):
    models: t.Dict[str, Model]
    select_cls = Select
    id_field = 'id'

    def __init__(self, conn: t.Any, name: str):
        self.conn = conn
        self.name = name

    @property
    def db(self):
        raise NotImplementedError

    @abstractmethod
    def get_output_from_document(self, r: Document, key: str, model: str):
        pass

    @abstractmethod
    def set_content_bytes(self, r, key, bytes_):
        pass

    @abstractmethod
    def unset_outputs(self, info):
        pass
