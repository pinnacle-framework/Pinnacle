import dataclasses as dc
import typing as t
from functools import cached_property

from overrides import override

from pinnacledb.base.configs import CFG
from pinnacledb.components.component import Component
from pinnacledb.components.datatype import DataType
from pinnacledb.misc.annotations import public_api


@public_api(stability='beta')
@dc.dataclass(kw_only=True)
class Schema(Component):
    """
    A component carrying the information
    about the types or `Encoders` of a `Table`
    {component_parameters}
    :param fields: A mapping of field names to types or `Encoders`
    """

    __doc__ = __doc__.format(component_parameters=Component.__doc__)

    type_id: t.ClassVar[str] = 'schema'
    fields: t.Mapping[str, DataType]

    def __post_init__(self, artifacts):
        assert self.identifier is not None, 'Schema must have an identifier'
        assert self.fields is not None, 'Schema must have fields'
        super().__post_init__(artifacts)

    @override
    def pre_create(self, db) -> None:
        '''
        Database pre create hook to add datatype to db.
        '''
        for v in self.fields.values():
            if isinstance(v, DataType):
                db.add(v)
        return super().pre_create(db)

    @property
    def raw(self):
        '''
        Get a dictionary of fields as key and datatype as value, This is used
        to create ibis tables.
        '''
        return {
            k: (v.identifier if not isinstance(v, DataType) else CFG.bytes_encoding)
            for k, v in self.fields.items()
        }

    @cached_property
    def encoded_types(self):
        '''
        List of fields of type `DataType`
        '''
        return [k for k, v in self.fields.items() if isinstance(v, DataType)]

    @cached_property
    def trivial(self):
        '''
        List of trivial fields
        '''
        return not any([isinstance(v, DataType) for v in self.fields.values()])

    @property
    def encoders(self):
        '''
        An iterable to list `Datatype` fields
        '''
        for v in self.fields.values():
            if isinstance(v, DataType):
                yield v

    def decode_data(self, data: t.Mapping[str, t.Any]) -> t.Mapping[str, t.Any]:
        """
        Decode data using the schema's encoders

        :param data: data to decode
        """

        if self.trivial:
            return data
        decoded = {}
        for k, v in data.items():
            if k in self.encoded_types:
                field = self.fields[k]
                assert isinstance(field, DataType)
                v = field.decode_data(v)
            decoded[k] = v
        return decoded

    def __call__(self, data: t.Mapping[str, t.Any]):
        """
        Encode data using the schema's encoders

        :param data: data to encode
        """
        if self.trivial:
            return data
        encoded_data = {}
        for k, v in data.items():
            if k in self.fields and isinstance(self.fields[k], DataType):
                field_encoder = self.fields[k]
                assert callable(field_encoder)
                encoded_data.update({k: field_encoder(v).encode()})
            else:
                encoded_data.update({k: v})
        return encoded_data
