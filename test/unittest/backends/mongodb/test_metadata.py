from test.utils.database import metadata as metadata_utils

import pytest
from pinnacle_mongodb.metadata import MongoMetaDataStore

from pinnacle import CFG

DATABASE_URL = CFG.metadata_stort or "mongomock://test_db"


@pytest.fixture
def metadata():
    store = MongoMetaDataStore(DATABASE_URL)
    yield store
    store.drop(force=True)


def test_component(metadata):
    metadata_utils.test_component(metadata)


def test_parent_child(metadata):
    metadata_utils.test_parent_child(metadata)


def test_job(metadata):
    metadata_utils.test_job(metadata)
