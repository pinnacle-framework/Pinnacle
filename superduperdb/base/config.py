"""
The classes in this file define the configuration variables for SuperDuperDB,
which means that this file gets imported before alost anything else, and
canot contain any other imports from this project.
"""
# TODO further simplify these configurations

import json
import os
import typing as t
from enum import Enum

from pydantic import Field

from .jsonable import Factory, JSONable

_CONFIG_IMMUTABLE = True


class BaseConfigJSONable(JSONable):
    def force_set(self, name, value):
        '''
        Forcefully setattr of BaseConfigJSONable instance

        NOTE: Not recommended to be used.
        '''
        super().__setattr__(name, value)

    def __setattr__(self, name, value):
        if not _CONFIG_IMMUTABLE:
            super().__setattr__(name, value)
            return
        raise AttributeError(
            "Config is immutable, please restart the client with updated config."
        )


class Retry(BaseConfigJSONable):
    """Describes how to retry using the `tenacity` library

    :param stop_after_attempt: The number of attempts to make
    :param wait_max: The maximum time to wait between attempts
    :param wait_min: The minimum time to wait between attempts
    :param wait_multiplier: The multiplier for the wait time between attempts
    """

    # TODO - add this to an API mixin instead of project level config

    stop_after_attempt: int = 2
    wait_max: float = 10.0
    wait_min: float = 4.0
    wait_multiplier: float = 1.0


class Apis(BaseConfigJSONable):
    """A container for API connections

    :param retry: A ``Retry`` object
    """

    retry: Retry = Factory(Retry)


class Cluster(BaseConfigJSONable):
    """Describes a connection to distributed work via Dask

    :param distributed: Whether to use distributed task management via Dask or not
    :param deserializers: A list of deserializers
    :param serializers: A list of serializers
    :param dask_scheduler: The Dask scheduler URI
    :param local: Whether the connection is local
    """

    # TODO - none of these are actually used apart from `dask`
    distributed: bool = False
    deserializers: t.List[str] = Factory(list)
    serializers: t.List[str] = Factory(list)
    dask_scheduler: str = 'tcp://localhost:8786'
    local: bool = True  # Use local as the default, because we want it for unit testing.
    backfill_batch_size: int = 100


class LogLevel(str, Enum):
    """Enumerate log severity level"""

    DEBUG = 'DEBUG'
    INFO = 'INFO'
    SUCCESS = "SUCCESS"
    WARN = 'WARN'
    ERROR = 'ERROR'


class LogType(str, Enum):
    """Enumerate the standard logs"""

    # SYSTEM uses the systems STDOUT and STDERR for printing the logs.
    # DEBUG, INFO, and WARN go to STDOUT.
    # ERROR goes to STDERR.
    SYSTEM = "SYSTEM"

    # LOKI a format that is compatible with the Loki Log aggregation system.
    LOKI = "LOKI"


class Logging(BaseConfigJSONable):
    """Describe how we are going to log. This isn't yet used.

    :param level: The log level
    :param type: The log type
    :param kwargs: Any additional keyword arguments
    """

    level: LogLevel = LogLevel.DEBUG
    type: LogType = LogType.SYSTEM
    kwargs: dict = Factory(dict)


class Server(BaseConfigJSONable):
    """Configure the SuperDuperDB server connection information

    :param host: The host for the connection
    :param port: The port for the connection
    :param protocol: The protocol for the connection
    """

    host: str = '127.0.0.1'
    port: int = 3223
    protocol: str = 'http'
    vector_search: str = 'http://localhost:8000'
    cdc: str = 'http://localhost:8001'

    @property
    def uri(self) -> str:
        return f'{self.protocol}://{self.host}:{self.port}'


class Downloads(BaseConfigJSONable):
    """
    Configure how downloads are saved in the database
    or to hybrid filestorage (references to filesystem from datastore)

    :param hybrid: Whether hybrid is being used
    :param root: The root for the connection
    """

    hybrid: bool = False
    root: str = 'data/downloads'


class Config(JSONable):
    """The data class containing all configurable pinnacledb values

    :param data_backend: The URI for the data backend
    :param vector_search: The configuration for the vector search {'in_memory', 'lance'}
    :param artifact_store: The URI for the artifact store
    :param metadata_store: The URI for the metadata store
    :param cluster: Settings distributed computing and change data capture
    :param apis: Settings for OPENAI and other APIs
    :param logging: Logging
    :param server: Settings for the experimental Rest server
    :param downloads: Settings for downloading files"""

    @property
    def self_hosted_vector_search(self) -> bool:
        return self.data_backend == self.vector_search

    data_backend: str = 'mongodb://pinnacle:pinnacle@localhost:27017/test_db'

    # The configuration for the vector search
    vector_search: 'str' = 'in_memory'  # "in_memory" / "lance"
    lance_home: str = os.path.join('.pinnacledb', 'vector_indices')

    artifact_store: t.Optional[str] = None
    metadata_store: t.Optional[str] = None
    cluster: Cluster = Factory(Cluster)
    apis: Apis = Factory(Apis)
    logging: Logging = Factory(Logging)
    server: Server = Factory(Server)
    downloads: Downloads = Factory(Downloads)

    #: Probability of validation fold
    fold_probability: float = 0.05

    # mode: development or production
    mode: str = Field(default='development', pattern='^(development|production)$')

    class Config(JSONable.Config):
        protected_namespaces = ()

    def __setattr__(self, name, value):
        if name == 'mode':
            raise AttributeError('Not allowed to change mode')

        if not _CONFIG_IMMUTABLE:
            super().__setattr__(name, value)
            return

        raise AttributeError(
            'Config is immutable in production mode,\
             please restart the client with updated config.'
        )

    @property
    def comparables(self):
        '''
        A dict of `self` excluding some defined attributes.
        '''
        _dict = self.dict()
        list(map(_dict.pop, ('cluster', 'server', 'apis', 'logging', 'mode')))
        return _dict

    def match(self, cfg: dict):
        '''
        Match the target cfg dict with `self` comparables dict.
        '''
        self_cfg = self.comparables
        return hash(json.dumps(self_cfg, sort_keys=True)) == hash(
            json.dumps(cfg, sort_keys=True)
        )

    def force_set(self, name, value):
        '''
        Brings immutable behaviour to `CFG` instance.

        CAUTION: Only use it in development mode with caution,
        as this can bring unexpected behaviour.
        '''
        parent = self
        names = name.split('.')
        if len(names) > 1:
            name = names[-1]
            for n in names[:-1]:
                parent = getattr(parent, n)
            parent.force_set(name, value)
        else:
            super().__setattr__(name, value)
