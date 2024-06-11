import base64
import dataclasses as dc
import hashlib
import inspect
import io
import json
import os
import pickle
import re
import typing as t
from abc import abstractstaticmethod

import dill

from pinnacledb import CFG
from pinnacledb.backends.base.artifacts import (
    ArtifactSavingError,
    _construct_file_id_from_uri,
)
from pinnacledb.base.config import BytesEncoding
from pinnacledb.base.leaf import Leaf
from pinnacledb.components.component import Component, ensure_initialized
from pinnacledb.misc.annotations import component
from pinnacledb.misc.hash import random_sha1
from pinnacledb.misc.special_dicts import SuperDuperFlatEncode

Decode = t.Callable[[bytes], t.Any]
Encode = t.Callable[[t.Any], bytes]

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer
    from pinnacledb.components.schema import Schema


class IntermediateType:
    """Intermediate data type # noqa."""

    BYTES = 'bytes'
    STRING = 'string'


def json_encode(object: t.Any, info: t.Optional[t.Dict] = None) -> str:
    """Encode the dict to a JSON string.

    :param object: The object to encode
    :param info: Optional information
    """
    return json.dumps(object)


def json_decode(b: str, info: t.Optional[t.Dict] = None) -> t.Any:
    """Decode the JSON string to an dict.

    :param b: The JSON string to decode
    :param info: Optional information
    """
    return json.loads(b)


def pickle_encode(object: t.Any, info: t.Optional[t.Dict] = None) -> bytes:
    """Encodes an object using pickle.

    :param object: The object to encode.
    :param info: Optional information.
    """
    return pickle.dumps(object)


def pickle_decode(b: bytes, info: t.Optional[t.Dict] = None) -> t.Any:
    """Decodes bytes using pickle.

    :param b: The bytes to decode.
    :param info: Optional information.
    """
    return pickle.loads(b)


def dill_encode(object: t.Any, info: t.Optional[t.Dict] = None) -> bytes:
    """Encodes an object using dill.

    :param object: The object to encode.
    :param info: Optional information.
    """
    return dill.dumps(object, recurse=True)


def dill_decode(b: bytes, info: t.Optional[t.Dict] = None) -> t.Any:
    """Decodes bytes using dill.

    :param b: The bytes to decode.
    :param info: Optional information.
    """
    return dill.loads(b)


def file_check(path: t.Any, info: t.Optional[t.Dict] = None) -> str:
    """Checks if a file path exists.

    :param path: The file path to check.
    :param info: Optional information.
    :raises ValueError: If the path does not exist.
    """
    if not (isinstance(path, str) and os.path.exists(path)):
        raise ValueError(f"Path '{path}' does not exist")
    return path


def torch_encode(object: t.Any, info: t.Optional[t.Dict] = None) -> bytes:
    """Saves an object in torch format.

    :param object: The object to encode.
    :param info: Optional information.
    """
    import torch

    from pinnacledb.ext.torch.utils import device_of

    if not isinstance(object, dict):
        previous_device = str(device_of(object))
        object.to('cpu')
        f = io.BytesIO()
        torch.save(object, f)
        object.to(previous_device)
    else:
        f = io.BytesIO()
        torch.save(object, f)

    return f.getvalue()


def torch_decode(b: bytes, info: t.Optional[t.Dict] = None) -> t.Any:
    """Decodes bytes to a torch model.

    :param b: The bytes to decode.
    :param info: Optional information.
    """
    import torch

    return torch.load(io.BytesIO(b))


def bytes_to_base64(bytes):
    """Converts bytes to base64.

    :param bytes: The bytes to convert.
    """
    return base64.b64encode(bytes).decode('utf-8')


def base64_to_bytes(encoded):
    """Decodes a base64 encoded string.

    :param encoded: The base64 encoded string.
    """
    return base64.b64decode(encoded)


class DataTypeFactory:
    """Abstract class for creating a DataType # noqa."""

    @abstractstaticmethod
    def check(data: t.Any) -> bool:
        """Check if the data can be encoded by the DataType.

        If the data can be encoded, return True, otherwise False

        :param data: The data to check
        """
        raise NotImplementedError

    @abstractstaticmethod
    def create(data: t.Any) -> "DataType":
        """Create a DataType for the data.

        :param data: The data to create the DataType for
        """
        raise NotImplementedError


class DataType(Component):
    """A data type component that defines how data is encoded and decoded.

    :param encoder: A callable that converts an encodable object of this
                    encoder to bytes.
    :param decoder: A callable that converts bytes to an encodable object
                    of this encoder.
    :param info: An optional information dictionary.
    :param shape: The shape of the data.
    :param directory: The directory to store file types.
    :param encodable: The type of encodable object ('encodable',
                      'lazy_artifact', or 'file').
    :param bytes_encoding: The encoding type for bytes ('base64' or 'bytes').
    :param intermediate_type: Type of the intermediate data
           [IntermediateType.BYTES, IntermediateType.STRING]
    :param media_type: The media type.
    """

    type_id: t.ClassVar[str] = 'datatype'
    encoder: t.Optional[t.Callable] = None  # not necessary if encodable is file
    decoder: t.Optional[t.Callable] = None
    info: t.Optional[t.Dict] = None
    shape: t.Optional[t.Sequence] = None
    directory: t.Optional[str] = None
    encodable: str = 'encodable'
    bytes_encoding: t.Optional[str] = CFG.bytes_encoding
    intermediate_type: t.Optional[str] = IntermediateType.BYTES
    media_type: t.Optional[str] = None
    registered_types: t.ClassVar[t.Dict[str, "DataType"]] = {}

    def __post_init__(self, db, artifacts):
        """Post-initialization hook.

        :param artifacts: The artifacts.
        """
        self.encodable_cls = _ENCODABLES[self.encodable]
        super().__post_init__(db, artifacts)
        self._takes_x = 'x' in inspect.signature(self.encodable_cls.__init__).parameters
        self.bytes_encoding = self.bytes_encoding or CFG.bytes_encoding
        self.register_datatype(self)

    def dict(self):
        """Get the dictionary representation of the object."""
        r = super().dict()
        if hasattr(self.bytes_encoding, 'value'):
            r['bytes_encoding'] = str(self.bytes_encoding.value)
        return r

    def __call__(
        self, x: t.Optional[t.Any] = None, uri: t.Optional[str] = None
    ) -> '_BaseEncodable':
        """Create an instance of the encodable class.

        :param x: The optional content.
        :param uri: The optional URI.
        """
        if self._takes_x:
            x = Empty() if x is None else x
            return self.encodable_cls(datatype=self, x=x, uri=uri, db=self.db)
        else:
            return self.encodable_cls(datatype=self, uri=uri, db=self.db)

    @ensure_initialized
    def encode_data(self, item, info: t.Optional[t.Dict] = None):
        """Encode the item into bytes.

        :param item: The item to encode.
        :param info: The optional information dictionary.
        """
        info = info or {}
        data = self.encoder(item, info) if self.encoder else item
        data = self.bytes_encoding_after_encode(data)
        return data

    @ensure_initialized
    def decode_data(self, item, info: t.Optional[t.Dict] = None):
        """Decode the item from bytes.

        :param item: The item to decode.
        :param info: The optional information dictionary.
        """
        info = info or {}
        item = self.bytes_encoding_before_decode(item)
        return self.decoder(item, info=info) if self.decoder else item

    def bytes_encoding_after_encode(self, data):
        """Encode the data to base64.

        if the bytes_encoding is BASE64 and the intermidia_type is BYTES

        :param data: Encoded data
        """
        if (
            self.bytes_encoding == BytesEncoding.BASE64
            and self.intermediate_type == IntermediateType.BYTES
        ):
            return bytes_to_base64(data)
        return data

    def bytes_encoding_before_decode(self, data):
        """Encode the data to base64.

        if the bytes_encoding is BASE64 and the intermidia_type is BYTES

        :param data: Decoded data
        """
        if (
            self.bytes_encoding == BytesEncoding.BASE64
            and self.intermediate_type == IntermediateType.BYTES
        ):
            return base64_to_bytes(data)
        return data

    @classmethod
    def register_datatype(cls, instance):
        """Register a datatype.

        :param instance: The datatype instance to register.
        """
        cls.registered_types[instance.identifier] = instance


def encode_torch_state_dict(module, info):
    """Encode torch state dictionary.

    :param module: Module.
    :param info: Information.
    """
    import torch

    buffer = io.BytesIO()
    torch.save(module.state_dict(), buffer)

    return buffer.getvalue()


class DecodeTorchStateDict:
    """Torch state dictionary decoder.

    :param cls: Torch state cls
    """

    def __init__(self, cls):
        self.cls = cls

    def __call__(self, b: bytes, info: t.Dict):
        """Decode the torch state dictionary.

        :param b: Bytes.
        :param info: Information.
        """
        import torch

        buffer = io.BytesIO(b)
        module = self.cls(**info)
        module.load_state_dict(torch.load(buffer))
        return module


def _find_descendants(cls):
    """Find descendants of the given class.

    :param cls: The class to find descendants for.
    """
    descendants = cls.__subclasses__()
    for subclass in descendants:
        descendants.extend(_find_descendants(subclass))
    return descendants


class _BaseEncodable(Leaf):
    """Data variable wrapping encode-able item.

    Encoding is controlled by the referred
    to ``Encoder`` instance.

    :param file_id: unique-id of the content
    :param datatype: The datatype of the content.
    :param uri: URI of the content, if any.
    :param sha1: SHA1 hash of the content.
    :param x: Wrapped content.
    """

    identifier: str = ''
    file_id: t.Optional[str] = None
    datatype: DataType
    uri: t.Optional[str] = None
    sha1: t.Optional[str] = None
    x: t.Optional[t.Any] = None
    lazy: t.ClassVar[bool] = False

    def __post_init__(self, db):
        """Post-initialization hook.

        :param db: Datalayer instance.
        """
        db = db or self.datatype.db
        super().__post_init__(db)
        if self.uri is not None and self.file_id is None:
            self.file_id = _construct_file_id_from_uri(self.uri)

        if self.uri and not re.match('^[a-z]{0,5}://', self.uri):
            self.uri = f'file://{self.uri}'

    @property
    def id(self):
        assert self.file_id is not None
        return f'{self.leaf_type}/{self.file_id}'

    @property
    def reference(self):
        """Get the reference to the datatype."""
        return self.datatype.reference

    def unpack(self):
        """Unpack the content of the `Encodable`."""
        return self.x

    @classmethod
    def get_encodable_cls(cls, name, default=None):
        """Get the subclass of the _BaseEncodable with the given name.

        All the registered subclasses must be subclasses of the _BaseEncodable.

        :param name: Name of the subclass.
        :param default: Default class to return if no subclass is found.
        :raises ValueError: If no subclass with the name is found and no default
                            is provided.
        """
        for sub_cls in _find_descendants(cls):
            if sub_cls.__name__.lower() == name.lower().replace('_', '').replace(
                '-', ''
            ):
                return sub_cls
        if default is None:
            raise ValueError(f'No subclass with name "{name}" found.')
        elif not issubclass(default, cls):
            raise ValueError(
                "The default class must be a subclass of the _BaseEncodable."
            )
        return default

    def get_hash(self, data):
        """Get the hash of the given data.

        :param data: Data to hash.
        """
        if isinstance(data, str):
            bytes_ = data.encode()
        elif isinstance(data, bytes):
            bytes_ = data
        else:
            raise ValueError(f'Unsupported data type: {type(data)}')
        return hashlib.sha1(bytes_).hexdigest()


class Empty:
    """Sentinel class # noqa."""

    def __repr__(self):
        """Get the string representation of the Empty object."""
        return '<EMPTY>'


class Encodable(_BaseEncodable):
    """Class for encoding non-Python datatypes to the database.

    :param x: The encodable object.
    :param blob: The blob data.
    """

    x: t.Any = Empty()
    blob: dc.InitVar[t.Optional[bytearray]] = None
    leaf_type: t.ClassVar[str] = 'encodable'

    def __post_init__(self, db, blob):
        super().__post_init__(db)
        if isinstance(self.x, Empty):
            self.datatype.init()
            self.x = self.datatype.decode_data(blob)

    def _encode(self):
        bytes_ = self.datatype.encode_data(self.x)
        sha1 = self.get_hash(bytes_)
        return bytes_, sha1

    def encode(self, schema: t.Optional['Schema'] = None):
        """Encode the object.

        :param schema: The schema to encode the object with.
        """
        cache: t.Dict[str, dict] = {}
        blobs: t.Dict[str, bytes] = {}
        files: t.Dict[str, str] = {}

        return SuperDuperFlatEncode(
            {
                '_base': self._deep_flat_encode(cache, blobs, files, (), schema),
                '_leaves': cache,
                '_blobs': blobs,
                '_files': files,
            }
        )

    def _deep_flat_encode(self, cache, blobs, files, leaves_to_keep=(), schema=None):
        if isinstance(self, leaves_to_keep):
            cache[self.id] = self
            return f'?{self.id}'

        maybe_bytes, file_id = self._encode()
        if schema is not None:
            return maybe_bytes

        self.file_id = file_id
        r = super()._deep_flat_encode(
            cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=schema
        )
        del r['x']
        r['blob'] = maybe_bytes
        cache[self.id] = r
        return f'?{self.id}'

    def init(self, db):
        """Initialization method.

        :param db: The Datalayer instance.
        """
        pass

    @classmethod
    def get_datatype(cls, db, r):
        """Get the datatype of the object.

        :param db: `Datalayer` instance to assist with
        :param r: The object to get the datatype from
        """
        if db is None:
            try:
                from pinnacledb.components.datatype import serializers

                datatype = serializers[r['datatype']]
            except KeyError:
                raise ValueError(
                    f'You specified a serializer which doesn\'t have a'
                    f' default value: {r["datatype"]}'
                )
        else:
            datatype = db.datatypes[r['datatype']]
        return datatype


class Native(_BaseEncodable):
    """Class for representing native data supported by the underlying database.

    :param x: The encodable object.
    """

    leaf_type: t.ClassVar[str] = 'native'
    x: t.Optional[t.Any] = None

    def __post_init__(self, db):
        return super().__post_init__(db)

    @classmethod
    def _get_object(cls, db, r):
        raise NotImplementedError

    def _deep_flat_encode(self, cache, blobs, files, leaves_to_keep=(), schema=None):
        return self.x

    @property
    def id(self):
        """Get the id of the object."""
        return f'{self.leaf_type}/{self.sha1}'


class Artifact(_BaseEncodable):
    """Class for representing data to be saved on disk or in the artifact-store.

    :param x: The artifact object.
    :param blob: The blob data. Can be a string or bytes.
                if string, it should be in the format `&:blob:{file_id}`
                if bytes, it should be the actual data.
    """

    leaf_type: t.ClassVar[str] = 'artifact'
    x: t.Any = Empty()
    blob: dc.InitVar[t.Optional[t.Union[str, bytes]]] = None
    lazy: t.ClassVar[bool] = False

    def __post_init__(self, db, blob=None):
        super().__post_init__(db)
        self._blob = blob

        if not self.lazy and isinstance(self.x, Empty):
            self.init()

        if self.datatype.bytes_encoding == BytesEncoding.BASE64:
            raise ArtifactSavingError('BASE64 not supported on disk!')

    @property
    def _id(self):
        assert self.file_id is not None
        return f':blob:{self.file_id}'

    def init(self, db=None):
        """Initialize to load `x` with the actual file from the artifact store."""
        self.db = self.db or db

        if not isinstance(self.x, Empty):
            return

        if isinstance(self._blob, str):
            self.file_id = self._blob.split('&:blob:')[-1]

        if isinstance(self._blob, bytes):
            blob = self._blob
        else:
            assert (
                self.file_id is not None
            ), 'file_id must be provided to init from database'
            assert self.db is not None, 'db must be provided to init from file_id'
            blob = self.db.artifact_store.get_bytes(self.file_id)

        self.datatype.init()
        self.x = self.datatype.decoder(blob)

    def _deep_flat_encode(self, cache, blobs, files, leaves_to_keep=(), schema=None):
        maybe_bytes = None
        if self.file_id is None:
            maybe_bytes, self.file_id = self._encode()

        if isinstance(self, leaves_to_keep):
            cache[self._id] = self
            return f'?{self._id}'

        if schema is not None:
            blobs[self.file_id] = maybe_bytes
            return f'?{self._id}'

        r = super()._deep_flat_encode(
            cache,
            blobs,
            files,
            leaves_to_keep=leaves_to_keep,
            schema=schema,
        )
        r['blob'] = f'?{self._id}'

        del r['x']
        if isinstance(maybe_bytes, bytes):
            blobs[self.file_id] = maybe_bytes
        cache[self.id] = r
        return f'?{self.id}'

    def _encode(self):
        bytes_ = self.datatype.encode_data(self.x)
        sha1 = self.get_hash(bytes_)
        return bytes_, sha1

    def unpack(self):
        """Unpack the content of the `Encodable`."""
        self.init()
        return self.x


class LazyArtifact(Artifact):
    """Data to be saved and loaded only when needed."""

    leaf_type: t.ClassVar[str] = 'lazy_artifact'
    lazy: t.ClassVar[bool] = True


class File(_BaseEncodable):
    """Data to be saved on disk and passed as a file reference.

    :param x: path to the file
    :param file_name: File name
    :param file: file reference, format `&:file:{file_name}/{file_id}
    """

    leaf_type: t.ClassVar[str] = 'file'
    x: t.Any = Empty()
    lazy: t.ClassVar[bool] = False
    file_name: t.Optional[str] = None
    file: dc.InitVar[t.Optional[bytearray]] = None

    def __post_init__(self, db, file=None):
        super().__post_init__(db)
        self._file = file

        if not self.lazy and isinstance(self.x, Empty):
            self.init()

    @property
    def _id(self):
        assert self.file_id is not None
        file_name = self.file_name.replace('.', '__')
        return f':file:{file_name}:{self.file_id}'

    def _deep_flat_encode(self, cache, blobs, files, leaves_to_keep=(), schema=None):
        self.file_id = self.file_id or random_sha1()

        if isinstance(self, leaves_to_keep):
            cache[self.id] = self
            return f'?{self.id}'

        if self.x not in files:
            files[self.file_id] = self.x

        self.file_name = os.path.basename(self.x.rstrip('/'))

        if schema is not None:
            files[self.file_id]
            return f'?{self._id}'

        r = super()._deep_flat_encode(
            cache, blobs, files, leaves_to_keep=(), schema=schema
        )
        r['file'] = f'?{self._id}'

        del r['x']

        cache[self.id] = r

        return f'?{self.id}'

    def init(self, db=None):
        """Initialize to load `x` with the actual file from the artifact store."""
        self.db = self.db or db
        if not isinstance(self.x, Empty):
            return

        if self._file is not None:
            # parse the file reference
            if self._file.startswith('&:file:'):
                file = self._file.replace('&:file:', '')
                *_, file_name, file_id = file.split(':')
                file_name = file_name.replace('__', '.')
                self.file_id = file_id
                self.file_name = file_name
            else:
                # Get the real path and return
                self.x = self._file
                return

        file_path = self.db.artifact_store.get_file(self.file_id)
        file_path = os.path.join(file_path, self.file_name)
        self.x = file_path

    def unpack(self):
        """Unpack and get the original data."""
        self.init()
        return self.x


class LazyFile(File):
    """Class is used to load a file only when needed."""

    leaf_type: t.ClassVar[str] = 'lazy_file'
    lazy: t.ClassVar[bool] = True


Encoder = DataType


_ENCODABLES = {
    'encodable': Encodable,
    'artifact': Artifact,
    'lazy_artifact': LazyArtifact,
    'file': File,
    'native': Native,
    'lazy_file': LazyFile,
}

json_serializer = DataType(
    'json',
    encoder=json_encode,
    decoder=json_decode,
    encodable='encodable',
    bytes_encoding=BytesEncoding.BASE64,
    intermediate_type=IntermediateType.STRING,
)

methods: t.Dict[str, t.Dict] = {
    'pickle': {'encoder': pickle_encode, 'decoder': pickle_decode},
    'dill': {'encoder': dill_encode, 'decoder': dill_decode},
    'torch': {'encoder': torch_encode, 'decoder': torch_decode},
    'file': {'encoder': file_check, 'decoder': file_check},
}


@component()
def get_serializer(
    identifier: str, method: str, encodable: str, db: t.Optional['Datalayer'] = None
):
    """Get a serializer.

    :param identifier: The identifier of the serializer.
    :param method: The method of the serializer.
    :param encodable: The type of encodable object.
    :param db: The Datalayer instance.
    """
    return DataType(
        identifier=identifier,
        encodable=encodable,
        db=db,
        **methods[method],
    )


pickle_encoder = get_serializer(
    identifier='pickle_encoder',
    method='pickle',
    encodable='encodable',
)


pickle_serializer = get_serializer(
    identifier='pickle',
    method='pickle',
    encodable='artifact',
)

pickle_lazy = get_serializer(
    identifier='pickle_lazy',
    method='pickle',
    encodable='lazy_artifact',
)

dill_serializer = get_serializer(
    identifier='dill',
    method='dill',
    encodable='artifact',
)

dill_lazy = get_serializer(
    identifier='dill_lazy',
    method='dill',
    encodable='lazy_artifact',
)

torch_serializer = get_serializer(
    identifier='torch',
    method='torch',
    encodable='lazy_artifact',
)

file_serializer = get_serializer(
    identifier='file',
    method='file',
    encodable='file',
)

file_lazy = get_serializer(
    identifier='file_lazy',
    method='file',
    encodable='lazy_file',
)

serializers = {
    'pickle': pickle_serializer,
    'dill': dill_serializer,
    'torch': torch_serializer,
    'file': file_serializer,
    'pickle_lazy': pickle_lazy,
    'dill_lazy': dill_lazy,
    'file_lazy': file_lazy,
}
