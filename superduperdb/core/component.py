# ruff: noqa: F821
import typing as t
from pinnacledb.core.job import ComponentJob
from pinnacledb.core.serializable import Serializable
import dataclasses as dc

Datalayer = 'pinnacledb.datalayer.base.datalayer.Datalayer'


@dc.dataclass
class Component(Serializable):
    """
    Base component which models, watchers, learning tasks etc. inherit from.

    :param identifier: Unique ID
    """

    variety: t.ClassVar[str]

    def _on_load(self, db):
        pass

    def _on_create(self, db):
        pass

    @property
    def child_components(self):
        return []

    @property
    def unique_id(self):
        if self.version is None:
            raise Exception('Version not yet set for component uniqueness')
        return f'{self.variety}/{self.identifier}/{self.version}'

    def dict(self):
        return dc.asdict(self)

    def create_validation_job(
        self,
        validation_set: t.Union[str, 'Dataset'],  # type: ignore[name-defined]
        metrics: t.List[str],
    ):
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

    def schedule_jobs(self, database, dependencies=()):
        return []

    @classmethod
    def make_unique_id(cls, variety, identifier, version):
        return f'{variety}/{identifier}/{version}'
