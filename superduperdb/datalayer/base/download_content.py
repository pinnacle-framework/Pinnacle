import typing as t

from pinnacledb.cluster.job_submission import work
from pinnacledb.core.documents import Document
from pinnacledb.datalayer.base.query import Insert, Select
from pinnacledb.fetchers.downloads import Downloader
from pinnacledb.fetchers.downloads import gather_uris
from pinnacledb.misc.logger import logging


@work
def download_content(
    db,
    query: t.Union[Select, Insert],
    ids=None,
    documents=None,
    timeout=None,
    raises=True,
    n_download_workers=None,
    headers=None,
    **kwargs,
):
    logging.debug(query)
    logging.debug(ids)
    update_db = False

    if documents is not None:
        pass
    elif isinstance(query, Select):
        update_db = True
        if ids is None:
            documents = list(db.select(query))
        else:
            select = query.select_using_ids(ids)
            select = select.copy(update={'raw': True})
            documents = list(db.select(select))
            documents = [Document(x) for x in documents]
    else:
        documents = query.documents

    documents = [x.content for x in documents]
    uris, keys, place_ids = gather_uris(documents)
    logging.info(f'found {len(uris)} uris')
    if not uris:
        return

    if n_download_workers is None:
        try:
            n_download_workers = db.metadata.get_metadata(key='n_download_workers')
        except TypeError:
            n_download_workers = 0

    if headers is None:
        try:
            headers = db.metadata.get_metadata(key='headers')
        except TypeError:
            headers = 0

    if timeout is None:
        try:
            timeout = db.metadata.get_metadata(key='download_timeout')
        except TypeError:
            timeout = None

    def update_one(id, key, bytes):
        return db.update(db.db.download_update(query.table, id, key, bytes))

    downloader = Downloader(
        uris=uris,
        ids=place_ids,
        keys=keys,
        update_one=update_one,
        n_workers=n_download_workers,
        timeout=timeout,
        headers=headers,
        raises=raises,
    )
    downloader.go()
    if update_db:
        return
    for id_, key in zip(place_ids, keys):
        documents[id_] = db.db.set_content_bytes(
            documents[id_], key, downloader.results[id_]
        )
    return documents
