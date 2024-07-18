from pinnacle.base.document import Document
import pytest

from test.db_config import DBConfig


@pytest.mark.parametrize("db", [DBConfig.mongodb_empty], indirect=True)
def test_load_image_inside_query(db, clean):
    r = {
        '_path': 'pinnacle.backends.base.query.parse_query', 
        'query': 'image-search.predict(documents[0]["img"])',
        'documents': [
            {'img': '?32b6853dd2b2b45de723966dba17e23cece9f35c'}
        ],
        '_builds': {
            'jpg': {
                '_path': 'pinnacle.ext.pillow.encoder.image_type',
                'encodable': 'artifact',
                'media_type': 'image/jpeg',
                'type_id': 'datatype',
            },
            '32b6853dd2b2b45de723966dba17e23cece9f35c': {
                '_path': 'pinnacle.components.datatype.Artifact',
                'datatype': '?jpg',
                'uri': None,
                'blob': '&:blob:32b6853dd2b2b45de723966dba17e23cece9f35c'
            }
        }
    }

    with pytest.raises(FileNotFoundError):  
        q = Document.decode(r, db=db).unpack()

    with open('test/material/data/test-image.jpeg', 'rb') as f:
        db.artifact_store.put_bytes(f.read(), '32b6853dd2b2b45de723966dba17e23cece9f35c')

    q = Document.decode(r, db=db).unpack()

    print(q)


@pytest.fixture
def clean():
    yield
    import os
    try:
        os.remove('/tmp/test_db/32b6853dd2b2b45de723966dba17e23cece9f35c')
    except FileNotFoundError:
        pass