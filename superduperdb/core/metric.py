import dataclasses as dc
import typing as t

from pinnacledb.core.artifact import Artifact
from pinnacledb.core.component import Component


@dc.dataclass
class Metric(Component):
    """
    Metric base object with which to evaluate performance on a data-set.
    These objects are ``callable`` and are applied row-wise to the data, and averaged.
    """

    variety: t.ClassVar[str] = 'metric'
    artifacts: t.ClassVar[t.List[str]] = ['object']

    identifier: str
    object: t.Union[Artifact, t.Callable, None] = None
    version: t.Optional[int] = None

    def __post_init__(self):
        if self.object and not isinstance(self.object, Artifact):
            self.object = Artifact(artifact=self.object)

    def __call__(self, x: int, y: int) -> bool:
        return self.object.artifact(x, y)
