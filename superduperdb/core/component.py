# ruff: noqa: F821
from __future__ import annotations
import typing as t
from pinnacledb.core.job import ComponentJob
from pinnacledb.core.serializable import Serializable
import dataclasses as dc

if t.TYPE_CHECKING:
    from pinnacledb.datalayer.base.datalayer import Datalayer
    from pinnacledb.datalayer.base.dataset import Dataset


@dc.dataclass
class Component(Serializable):
    """
    Base component which models, watchers, learning tasks etc. inherit from.

    :param identifier: Unique ID
    """

    variety: t.ClassVar[str]

    def on_create(self, db: Datalayer) -> None:
        """Called the first time this component is created

        :param db: the datalayer that created the component
        """
        pass

    def on_load(self, db: Datalayer) -> None:
        """Called when this component is loaded from the data store

        :param db: the datalayer that loaded the component
        """
        pass

    @property
    def child_components(self) -> t.Sequence[t.Any]:
        return []

    @property
    def unique_id(self) -> str:
        if self.version is None:
            raise Exception('Version not yet set for component uniqueness')
        return f'{self.variety}/{self.identifier}/{self.version}'

    def dict(self) -> t.Dict[str, t.Any]:
        return dc.asdict(self)

    def create_validation_job(
        self,
        validation_set: t.Union[str, Dataset],
        metrics: t.Sequence[str],
    ) -> ComponentJob:
        return ComponentJob(
            component_identifier=self.identifier,
            method_name='predict',
            variety='model',
            kwargs={
                'distributed': False,
                'validation_set': validation_set,
                'metrics': metrics,
            },
        )

    def schedule_jobs(
        self, database: Datalayer, dependencies: t.Sequence[()] = ()
    ) -> t.Sequence[t.Any]:
        return []

    @classmethod
    def make_unique_id(cls, variety: str, identifier: str, version: int) -> str:
        return f'{variety}/{identifier}/{version}'
