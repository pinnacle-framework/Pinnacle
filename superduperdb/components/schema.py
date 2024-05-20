import dataclasses as dc
import typing as t
from functools import cached_property

from overrides import override

from pinnacledb.components.component import Component
from pinnacledb.components.datatype import DataType
from pinnacledb.misc.special_dicts import SuperDuperFlatEncode
from pinnacledb.misc.annotations import public_api

class _Native:
    _TYPES = {str: 'str', int: 'int', float: 'float'}
    def __init__(self, x):
        if x in self._TYPES:
            x = self._TYPES[x]
        self.identifier =  x

@public_api(stability='beta')
@dc.dataclass(kw_only=True)
class Schema(Component):
    """A component containing information about the types or encoders of a table.

    {component_parameters}
    :param fields: A mapping of field names to types or encoders.
    """

    __doc__ = __doc__.format(component_parameters=Component.__doc__)

    type_id: t.ClassVar[str] = 'schema'
    fields: t.Mapping[str, DataType]

    def __post_init__(self, db, artifacts):
        assert self.identifier is not None, 'Schema must have an identifier'
        assert self.fields is not None, 'Schema must have fields'
        super().__post_init__(db, artifacts)

        for k, v in self.fields.items():
            if isinstance(v, str):
                self.fields[k] = _Native(v)
            elif v in (str, bool, int, float):
                self.fields[k] = _Native(v)


    @override
    def pre_create(self, db) -> None:
        """Database pre-create hook to add datatype to the database.

        :param db: Datalayer instance.
        """
        for v in self.fields.values():
            if isinstance(v, DataType):
                db.add(v)
        return super().pre_create(db)

    @property
    def raw(self):
        """Return the raw fields.

        Get a dictionary of fields as keys and datatypes as values.
        This is used to create ibis tables.
        """
        return {
            k: (v.identifier if not isinstance(v, DataType) else v.bytes_encoding)
            for k, v in self.fields.items()
        }

    def deep_flat_encode_data(self, r, cache, blobs, files, leaves_to_keep=None):
        for k in self.fields:
            if isinstance(self.fields[k], DataType):
                encodable = self.fields[k](r[k])
                if isinstance(encodable, leaves_to_keep):
                    continue
                r[k] = encodable._deep_flat_encode(
                    cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=self
                )
        return r

    @cached_property
    def encoded_types(self):
        """List of fields of type DataType."""
        return [k for k, v in self.fields.items() if isinstance(v, DataType)]

    @cached_property
    def trivial(self):
        """Determine if the schema contains only trivial fields."""
        return not any([isinstance(v, DataType) for v in self.fields.values()])

    @property
    def encoders(self):
        """An iterable to list DataType fields."""
        for v in self.fields.values():
            if isinstance(v, DataType):
                yield v

    def decode_data(self, data: dict[str, t.Any]) -> dict[str, t.Any]:
        """Decode data using the schema's encoders.

        :param data: Data to decode.
        """
        if self.trivial:
            return data

        decoded = {}
        for k in data.keys():
            if isinstance(field := self.fields.get(k), DataType):
                # TODO: We need to sort out the logic here
                # We use encodable_cls to encode the data, but we the decoder here
                # decoded[k] = field.encodable_cls.decode(data[k])
                decoded[k] = field.decoder(data[k])
            else:
                decoded[k] = data[k]
        return decoded

    def __call__(self, data: dict[str, t.Any]) -> dict[str, t.Any]:
        """Encode data using the schema's encoders.

        :param data: Data to encode.
        """
        if self.trivial:
            return data

        encoded_data = {}
        cache = {}
        files = {}
        blobs = {}
        for k, v in data.items():
            if k in self.fields and isinstance(self.fields[k], DataType):
                field_encoder = self.fields[k]
                assert callable(field_encoder)
                v = field_encoder(v).encode()
                base = v['_base']
                cache.update(v['_leaves'])
                blobs.update(v.get('_blobs', {}))
                files.update(v.get('_files', {}))
                encoded_data.update({k: base})
            else:
                encoded_data.update({k: v})
        encoded_data['_leaves'] = cache
        encoded_data['_blobs'] = blobs
        encoded_data['_files'] = files
        return SuperDuperFlatEncode(encoded_data)
