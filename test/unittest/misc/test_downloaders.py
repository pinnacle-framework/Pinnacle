import os
import tempfile
import uuid
from test.db_config import DBConfig

import pytest

from pinnacledb import CFG
from pinnacledb.backends.mongodb.query import MongoQuery
from pinnacledb.base.document import Document
from pinnacledb.ext.pillow.encoder import pil_image_hybrid
from pinnacledb.misc.download import Fetcher

remote = os.environ.get('SDDB_REMOTE_TEST', 'local')


def test_s3_and_web():
    if remote == 'remote':
        Fetcher()('s3://pinnacledb-bucket/img/black.png')


@pytest.fixture
def patch_cfg_downloads(monkeypatch):
    td = str(uuid.uuid4())
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(CFG.downloads, 'folder', td)
        yield


# TODO: use table to test the sqldb
@pytest.mark.parametrize("db", [DBConfig.mongodb_empty], indirect=True)
def test_file_blobs(db, patch_cfg_downloads, image_url):
    to_insert = [
        Document(
            {
                'item': {
                    '_content': {
                        'uri': image_url,
                        'datatype': 'pil_image_hybrid',
                        'leaf_type': 'encodable',
                    }
                },
                'other': {
                    'item': {
                        '_content': {
                            'uri': image_url,
                            'datatype': 'pil_image_hybrid',
                            'leaf_type': 'encodable',
                        }
                    }
                },
            }
        )
        for _ in range(2)
    ]

    db.execute(
        MongoQuery('documents').insert_many(to_insert), datatypes=(pil_image_hybrid,)
    )
    r = db.execute(MongoQuery('documents').find_one())

    import PIL.PngImagePlugin

    assert isinstance(r.unpack()['item'], PIL.PngImagePlugin.PngImageFile)
