from test.db_config import DBConfig

import pytest

from pinnacle.components.component import Component
from pinnacle.components.listener import Listener
from pinnacle.components.model import ObjectModel
from pinnacle.components.template import QueryTemplate, Template


@pytest.mark.parametrize('db', [DBConfig.mongodb], indirect=True)
def test_basic_template(db):
    def model(x):
        return x + 2

    m = Listener(
        model=ObjectModel(
            object=model,
            identifier='<var:model_id>',
        ),
        select=db['documents'].find(),
        key='<var:key>',
    )

    # Optional "info" parameter provides details about usage
    # (depends on developer use-case)
    template = Template(
        identifier='my-template',
        template=m.encode(),
    )

    vars = template.template_variables
    assert len(vars) == 2
    assert all([v in ['key', 'model_id'] for v in vars])
    db.apply(template)

    # Check template component has not been added to metadata
    assert 'my_id' not in db.show('model')
    assert all([ltr.split('/')[-1] != m.identifier for ltr in db.show('listener')])
    listener = template(key='y', model_id='my_id')

    assert listener.key == 'y'
    assert listener.model.identifier == 'my_id'

    db.apply(listener)

    reloaded_template = db.load('template', template.identifier)
    listener = reloaded_template(key='y', model_id='my_id')

    db.apply(listener)

    listener.init()
    assert listener.model.object(3) == 5

    # Check listener outputs with key and model_id
    # TODO: Need to support MongoDB query.outputs()
    r = db['documents'].find_one().execute()
    o = db[listener.outputs].find_one().execute()
    assert o[listener.outputs_key] == r['y'] + 2


@pytest.mark.parametrize('db', [DBConfig.mongodb], indirect=True)
def test_template_export(db):
    m = Listener(
        model=ObjectModel(
            object=lambda x: x + 2,
            identifier='<var:model_id>',
        ),
        select=db['<var:collection>'].find(),
        key='<var:key>',
    )

    # Optional "info" parameter provides details about usage
    # (depends on developer use-case)
    t = Template(
        identifier='my-template',
        template=m.encode(),
    )

    db.apply(t)

    t = db.load('template', t.identifier)

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        t.export(temp_dir)

        rt = Component.read(temp_dir, db=db)
        db.apply(rt)

        listener = rt(key='y', model_id='my_id', collection='documents')

        assert listener.key == 'y'
        assert listener.model.identifier == 'my_id'
        assert listener.select.table == 'documents'

        db.apply(listener)
        # Check listener outputs with key and model_id
        # TODO: Need to support MongoDB query.outputs()
        r = db['documents'].find_one().execute()
        o = db[listener.outputs].find_one().execute()
        assert o[listener.outputs_key] == r['y'] + 2


@pytest.mark.parametrize('db', [DBConfig.mongodb], indirect=True)
def test_from_template(db):
    m = Listener(
        model=ObjectModel(
            object=lambda x: x + 2,
            identifier='<var:model_id>',
        ),
        select=db['<var:collection>'].find(),
        key='<var:key>',
    )
    component = Component.from_template(
        identifier='test-from-template',
        template_body=m.encode(),
        key='y',
        model='my_id',
    )

    component.init()
    assert isinstance(component, Listener)
    assert isinstance(component.model, ObjectModel)
    assert component.model.object(3) == 5


@pytest.mark.parametrize('db', [DBConfig.mongodb], indirect=True)
def test_query_template(db):
    q = db['documents'].find({'this': 'is a <var:test>'}).limit('<var:limit>')
    t = QueryTemplate('select_lim', template=q)

    assert set(t.template_variables) == {'limit', 'test'}
    assert t.template['query'] == 'documents.find(documents[0]).limit("<var:limit>")'
