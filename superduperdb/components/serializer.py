import dataclasses as dc
import typing as t

from pinnacledb.components.component import Component
from pinnacledb.misc.annotations import public_api
from pinnacledb.misc.serialization import serializers

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer


@public_api(stability='beta')
@dc.dataclass
class Serializer(Component):
    identifier: str
    object: t.Type

    type_id: t.ClassVar[str] = 'serializer'

    version: t.Optional[int]

    def pre_create(self, db: 'Datalayer'):
        serializers.add(self.identifier, self.object)

        self.object = t.cast(t.Type, self.identifier)
