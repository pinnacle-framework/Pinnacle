import dataclasses as dc
from functools import cached_property
import typing as t

from pinnacledb.container.component import Component
from pinnacledb.container.encoder import Encoder


@dc.dataclass
class Schema(Component):
    identifier: str
    fields: t.Mapping[str, t.Union[str, Encoder]]

    @cached_property
    def trivial(self):
        return not any([isinstance(v, Encoder) for v in self.fields.values()])

    def decode(self, data: t.Mapping[str, t.Any]) -> t.Mapping[str, t.Any]:
        if self.trivial:
            return data
        return {
            k: (self.fields[k].decode(v) if isinstance(self.fields[k], Encoder) else v)
            for k, v in data.items()
        }

    def encode(self, data):
        if self.trivial:
            return data
        return {
            k: (self.fields[k].encode.artifact(v) if isinstance(self.fields[k], Encoder) else v)
            for k, v in data.items()
        }
