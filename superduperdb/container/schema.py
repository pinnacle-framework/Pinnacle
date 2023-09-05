import dataclasses as dc
import typing as t
from functools import cached_property

from pinnacledb.container.component import Component
from pinnacledb.container.encoder import Encoder


@dc.dataclass
class Schema(Component):
    type_id: t.ClassVar[str] = 'schema'
    identifier: str
    fields: t.Mapping[str, t.Union[Encoder, str]]
    encoded_types: t.ClassVar[t.List] = dc.field(default_factory=list)

    @cached_property
    def trivial(self):
        return not any([isinstance(v, Encoder) for v in self.fields.values()])

    @property
    def encoders(self):
        for v in self.fields.values():
            if isinstance(v, Encoder):
                yield v

    def decode(self, data: t.Mapping[str, t.Any]) -> t.Mapping[str, t.Any]:
        if self.trivial:
            return data
        decoded = {}
        for k, v in data.items():
            if k in self.encoded_types:
                field = t.cast(Encoder, self.fields[k])
                v = field.decode(v)
            decoded[k] = v
        return decoded

    def encode(self, data):
        if self.trivial:
            return data
        return {
            k: (
                self.fields[k].encode.artifact(v)
                if isinstance(self.fields[k], Encoder)
                else v
            )
            for k, v in data.items()
        }
