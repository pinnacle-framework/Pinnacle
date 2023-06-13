import pytest
import numpy

from typing import Iterator

from pinnacledb.misc.config import VectorSearchConfig
from pinnacledb.vector_search.base import VectorIndexItem, VectorIndexItemNotFound
from pinnacledb.vector_search.inmemory import (
    InMemoryVectorIndexManager,
    VectorIndexManager,
)


class TestInMemoryVectorIndex:
    @pytest.fixture
    def manager(self) -> Iterator[VectorIndexManager]:
        with InMemoryVectorIndexManager(config=VectorSearchConfig()).init() as manager:
            yield manager

    def test_find_nearest_from_array(self, manager: InMemoryVectorIndexManager) -> None:
        with manager.get_index("test", dimensions=1) as index:
            index.add(
                [
                    VectorIndexItem(id=str(i), vector=numpy.array([i * 100]))
                    for i in range(100)
                ]
            )

            results = index.find_nearest_from_array(numpy.array([0]), limit=8)
            assert len(results) == 8
            ids = [int(r.id) for r in results]
            assert all(i <= 15 for i in ids)

    def test_find_nearest_from_id(self, manager: InMemoryVectorIndexManager) -> None:
        with manager.get_index("test", dimensions=1) as index:
            index.add(
                [
                    VectorIndexItem(id=str(i), vector=numpy.array([i]))
                    for i in range(100)
                ]
            )

            results = index.find_nearest_from_id("15", limit=8)
            assert len(results) == 8
            ids = [int(r.id) for r in results]
            assert all(5 <= i <= 25 for i in ids)

    def test_find_nearest_from_array__limit_offset(
        self, manager: InMemoryVectorIndexManager
    ) -> None:
        with manager.get_index("test", dimensions=1) as index:
            index.add(
                [
                    VectorIndexItem(id=str(i), vector=numpy.array([i * 100]))
                    for i in range(100)
                ]
            )

            for offset in range(10):
                results = index.find_nearest_from_array(
                    numpy.array([0]), limit=1, offset=offset
                )
                assert len(results) == 1
                ids = [int(r.id) for r in results]
                assert ids == [offset]

    def test_find_nearest_from_id__not_found(
        self, manager: InMemoryVectorIndexManager
    ) -> None:
        with manager.get_index("test", dimensions=1) as index:
            with pytest.raises(VectorIndexItemNotFound):
                index.find_nearest_from_id("15")

    def test_add__overwrite(self, manager: InMemoryVectorIndexManager) -> None:
        with manager.get_index("test", dimensions=1) as index:
            index.add([VectorIndexItem(id="0", vector=numpy.array([0]))])
            index.add([VectorIndexItem(id="1", vector=numpy.array([1]))])

            index.add([VectorIndexItem(id="1", vector=numpy.array([100]))])

            results = index.find_nearest_from_array(numpy.array([99]), limit=1)
            ids = [int(r.id) for r in results]
            assert ids == [1]
