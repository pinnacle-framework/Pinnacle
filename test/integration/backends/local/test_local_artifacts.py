import PIL.Image
import PIL.PngImagePlugin
import pytest

from pinnacledb import CFG
from pinnacledb.backends.mongodb import MongoQuery
from pinnacledb.base.document import Document

DO_SKIP = not CFG.data_backend.startswith("mongodb")


@pytest.fixture
def image(test_db):
    img = PIL.Image.open('test/material/data/test.png')
    from pinnacledb.ext.pillow.encoder import image_type

    _, i = test_db.add(image_type('image'))

    insert = MongoQuery('images').insert_one(Document({'img': i(img)}))

    test_db.execute(insert)

    yield test_db

    img.close()

    test_db.databackend.conn.test_db.drop_collection('images')


@pytest.mark.skipif(DO_SKIP, reason="skipping test if not mongodb")
def test_save_artifact(image):
    r = image.execute(MongoQuery('images').find_one())

    r = r.unpack(db=image)

    assert isinstance(r['img'], PIL.PngImagePlugin.PngImageFile)
