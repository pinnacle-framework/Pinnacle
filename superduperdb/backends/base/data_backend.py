import typing as t
from abc import ABC, abstractmethod

from pinnacledb.backends.ibis.field_types import FieldType
from pinnacledb.components.datatype import DataType


class BaseDataBackend(ABC):
    """Base data backend for the database.

    :param conn: The connection to the databackend database.
    :param name: The name of the databackend.
    """

    db_type = None

    def __init__(self, conn: t.Any, name: str):
        self.conn = conn
        self.name = name
        self.in_memory: bool = False
<<<<<<< HEAD
        self.in_memory_tables: t.Dict = {}
=======
        self._datalayer = None
>>>>>>> 9d83d21ec (Deprecate Serializable)

    @property
    def db(self):
        """Return the datalayer."""
        raise NotImplementedError

    @property
    def datalayer(self):
        return self._datalayer

    @datalayer.setter
    def datalayer(self, value):
        self._datalayer = value

    @abstractmethod
    def url(self):
        """Databackend connection url."""
        pass

    @abstractmethod
    def build_metadata(self):
        """Build a default metadata store based on current connection."""
        pass

    @abstractmethod
    def build_artifact_store(self):
        """Build a default artifact store based on current connection."""
        pass

    @abstractmethod
    def create_output_dest(
        self,
        predict_id: str,
        datatype: t.Union[None, DataType, FieldType],
        flatten: bool = False,
    ):
        """Create an output destination for the database.

        :param predict_id: The predict id of the output destination.
        :param datatype: The datatype of the output destination.
        :param flatten: Whether to flatten the output destination.
        """
        pass

    @abstractmethod
    def check_output_dest(self, predict_id) -> bool:
        """Check if the output destination exists.

        :param predict_id: The identifier of the output destination.
        """
        pass

    @abstractmethod
    def get_query_builder(self, key):
        pass

    @abstractmethod
    def get_table_or_collection(self, identifier):
        """Get a table or collection from the database.

        :param identifier: The identifier of the table or collection.
        """
        pass

    def set_content_bytes(self, r, key, bytes_):
        """Set content bytes.

        :param r: The row.
        :param key: The key.
        :param bytes_: The bytes.
        """
        raise NotImplementedError

    @abstractmethod
    def drop(self, force: bool = False):
        """Drop the databackend.

        :param force: If ``True``, don't ask for confirmation.
        """

    @abstractmethod
    def disconnect(self):
        """Disconnect the client."""

    @abstractmethod
    def list_tables_or_collections(self):
        """List all tables or collections in the database."""

    @staticmethod
    def infer_schema(data: t.Mapping[str, t.Any], identifier: t.Optional[str] = None):
        """Infer a schema from a given data object.

        :param data: The data object
        :param identifier: The identifier for the schema, if None, it will be generated
        :return: The inferred schema
        """
