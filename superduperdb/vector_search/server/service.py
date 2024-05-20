import math
import typing as t
import base64

from fastapi import Request

from pinnacledb.misc.auto_schema import DEFAULT_DATATYPE
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.vector_search.base import VectorItem

ListVectorType = t.Union[t.List[t.Union[float, int]], t.Dict]

VectorSearchResultType = t.Tuple[t.List[str], t.List[float]]


def _vector_search(
    x: t.Union[str, ListVectorType],
    n: int,
    vector_index: str,
    db: Datalayer,
    by_array: bool = True,
) -> VectorSearchResultType:
    vi = db.fast_vector_searchers[vector_index]
    if by_array:
        x = x['b64data']
        x = DEFAULT_DATATYPE.decoder(  base64.b64decode(x))
        ids, scores = vi.searcher.find_nearest_from_array(x, n=n)
    else:
        ids, scores = vi.searcher.find_nearest_from_id(x, n=n)
    scores = [-1.0 if math.isnan(s) else s for s in scores]
    return ids, scores


def database(request: Request) -> Datalayer:
    """Helper function to get the database instance from the app state.

    :param request: request object
    """
    return request.app.state.pool


def list_search(db: Datalayer):
    """Helper functon for listing all vector search indices.

    :param db: Datalayer instance
    """
    return db.show('vector_index')


def post_create(vector_index: str, db: Datalayer):
    """Post create method for vector searcher.

    Performs post create method of vector searcher to incorporate remaining vectors
    to be added in cache.

    :param vector_index: Vector class to initiate
    :param db: Datalayer instance
    """
    vi = db.fast_vector_searchers[vector_index]
    vi.post_create()


def create_search(vector_index: str, db: Datalayer):
    """Initiates a vector search class corresponding to `vector_index`.

    :param vector_index: Vector class to initiate
    :param db: Datalayer instance
    """
    db.fast_vector_searchers.update(
        {vector_index: db.initialize_vector_searcher(vector_index)}
    )


def query_search_from_array(
    array: ListVectorType,
    vector_index: str,
    db: Datalayer,
    n: int = 100,
) -> VectorSearchResultType:
    """Perform a vector search with an array.

    :param array: Array to perform vector search on index.
    :param vector_index: Vector search index
    :param db: Datalayer instance
    :param n: Number of nearest neighbors to be returned
    """
    return _vector_search(array, n=n, vector_index=vector_index, db=db)


def query_search_from_id(
    id: str, vector_index: str, db: Datalayer, n: int = 100
) -> VectorSearchResultType:
    """Perform a vector search with an id.

    :param id: Identifier for vector
    :param vector_index: Vector search index
    :param db: Datalayer instance
    :param n: Number of nearest neighbors to be returned
    """
    return _vector_search(id, n=n, vector_index=vector_index, db=db, by_array=False)


def add_search(vector, vector_index: str, db: Datalayer):
    """Adds a vector in vector index `vector_index`.

    :param vector: Vector to be added.
    :param vector_index: Vector index where vector needs to be added.
    :param db: Datalayer instance
    """
    vector = [VectorItem(id=v.id, vector=v.vector) for v in vector]

    vi = db.fast_vector_searchers[vector_index]
    vi.searcher.add(vector)


def delete_search(ids: t.List[str], vector_index: str, db: Datalayer):
    """Deletes a vector corresponding to `id`.

    :param ids: List of ids to be deleted.
    :param vector_index: Vector index where vector needs to be deleted.
    :param db: Datalayer instance
    """
    vi = db.fast_vector_searchers[vector_index]
    vi.searcher.delete(ids)
