import datetime
from functools import cached_property
import typing as t

import numpy

from pinnacledb.core.artifact import Artifact
from pinnacledb.core.component import Component
from pinnacledb.core.documents import Document
from pinnacledb.datalayer.mongodb.query import Find
import dataclasses as dc


@dc.dataclass
class Dataset(Component):
    variety: t.ClassVar[str] = 'dataset'

    identifier: str
    select: t.Optional[Find] = None
    sample_size: t.Optional[int] = None
    random_seed: t.Optional[int] = None
    creation_date: t.Optional[str] = None
    raw_data: t.Optional[t.Union[Artifact, t.Any]] = None
    version: t.Optional[int] = None
    db: dc.InitVar[t.Optional[t.Any]] = None

    def __post_init__(self, db):
        if self.creation_date is None:
            self.creation_date = str(datetime.datetime.now())
        if self.raw_data is None:
            data = list(db.execute(self.select))
            if self.sample_size is not None and self.sample_size < len(data):
                perm = self.random.permutation(len(data)).tolist()
                data = [data[perm[i]] for i in range(self.sample_size)]
            self.raw_data = Artifact(_artifact=[r.encode() for r in data])

        self.data = [
            Document(Document.decode(r, types=db.types)) for r in self.raw_data.a
        ]

    @cached_property
    def random(self):
        return numpy.random.default_rng(seed=self.random_seed)
