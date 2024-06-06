from __future__ import annotations

import typing as t
from functools import cached_property

import numpy

from pinnacledb.backends.base.query import Query
from pinnacledb.components.component import Component, ensure_initialized
from pinnacledb.components.datatype import (
    DataType,
    dill_serializer,
)


class Dataset(Component):
    """A dataset is an immutable collection of documents.

    :param select: A query to select the documents for the dataset.
    :param sample_size: The number of documents to sample from the query.
    :param random_seed: The random seed to use for sampling.
    :param creation_date: The date the dataset was created.
    """

    type_id: t.ClassVar[str] = 'dataset'
    _artifacts: t.ClassVar[t.Sequence[t.Tuple[str, DataType]]] = (
        ('raw_data', dill_serializer),
    )

    select: t.Optional[Query] = None
    sample_size: t.Optional[int] = None
    random_seed: t.Optional[int] = None
    creation_date: t.Optional[str] = None

    def __post_init__(self, db, artifacts):
        """Post-initialization method.

        :param artifacts: Optional additional artifacts for initialization.
        """
        self._data = None
        return super().__post_init__(db, artifacts)

    @property
    @ensure_initialized
    def data(self):
        """Property representing the dataset's data."""
        return self._data

    def init(self, db=None):
        """Initialization method."""
        super().init(db=db)
        if self._data is None:
            if self.select is None:
                raise ValueError('Select cannot be None')
            data = list(self.db.execute(self.select))
            if self.sample_size is not None and self.sample_size < len(data):
                perm = self.random.permutation(len(data)).tolist()
                data = [data[perm[i]] for i in range(self.sample_size)]
            self._data = data

    @cached_property
    def random(self):
        """Cached property representing the random number generator."""
        return numpy.random.default_rng(seed=self.random_seed)

    def __str__(self):
        """String representation of the dataset."""
        return f'Dataset(identifier={self.identifier}, select={self.select})'

    __repr__ = __str__
