import dataclasses as dc
import json
import typing as t

import magic
from fastapi import File, Response

from pinnacledb import CFG, logging
from pinnacledb.backends.base.query import Delete, Insert
from pinnacledb.base.document import Document
from pinnacledb.components.component import Component, import_
from pinnacledb.components.datatype import DataType
from pinnacledb.components.listener import Listener
from pinnacledb.components.model import (
    CodeModel,
    ObjectModel,
    QueryModel,
    SequentialModel,
)
from pinnacledb.components.stack import Stack
from pinnacledb.components.vector_index import VectorIndex, vector
from pinnacledb.ext import openai, sentence_transformers
from pinnacledb.ext.llm.prompter import RetrievalPrompt
from pinnacledb.ext.pillow.encoder import image_type
from pinnacledb.ext.sklearn.model import Estimator
from pinnacledb.ext.torch.model import TorchModel
from pinnacledb.rest.utils import parse_query, strip_artifacts
from pinnacledb.server import app as pinnacleapp

assert isinstance(
    CFG.cluster.rest.uri, str
), "cluster.rest.uri should be set with a valid uri"
port = int(CFG.cluster.rest.uri.split(':')[-1])

app = pinnacleapp.SuperDuperApp('rest', port=port)


@dc.dataclass(kw_only=True)
class MyBoolean(Component):
    type_id: t.ClassVar[str] = 'bool'
    my_bool: bool

    ui_schema: t.ClassVar[t.List[t.Dict]] = [
        {'name': 'my_bool', 'type': 'bool'},
        {'name': 'my_artifact', 'type': 'artifact', 'sequence': True},
        {
            'name': 'my_choice',
            'type': 'str',
            'sequence': True,
            'choices': ['a', 'b', 'c'],
        },
    ]


CLASSES: t.Dict[str, t.Dict[str, t.Any]] = {
    'bool': {'MyBoolean': MyBoolean},
    'model': {
        'ObjectModel': ObjectModel,
        'SequentialModel': SequentialModel,
        'QueryModel': QueryModel,
        'CodeModel': CodeModel,
        'RetrievalPrompt': RetrievalPrompt,
        'TorchModel': TorchModel,
        'SklearnEstimator': Estimator,
        'OpenAIEmbedding': openai.OpenAIEmbedding,
        'OpenAIChatCompletion': openai.OpenAIChatCompletion,
        'SentenceTransformer': sentence_transformers.SentenceTransformer,
    },
    'listener': {
        'Listener': Listener,
    },
    'datatype': {
        'image': image_type,
        'vector': vector,
        'DataType': DataType,
    },
    'vector-index': {'VectorIndex': VectorIndex},
}

FLAT_CLASSES = {}
for k in CLASSES:
    for sub in CLASSES[k]:
        FLAT_CLASSES[sub] = CLASSES[k][sub]


MODULE_LOOKUP: t.Dict[str, t.Dict[str, t.Any]] = {}
API_SCHEMAS: t.Dict[str, t.Dict[str, t.Any]] = {}
for type_id in CLASSES:
    API_SCHEMAS[type_id] = {}
    MODULE_LOOKUP[type_id] = {}
    for cls_name in CLASSES[type_id]:
        cls = CLASSES[type_id][cls_name]
        API_SCHEMAS[type_id][cls_name] = cls.get_ui_schema()
        MODULE_LOOKUP[type_id][cls_name] = cls.__module__


logging.info(json.dumps(API_SCHEMAS, indent=2))


def build_app(app: pinnacleapp.SuperDuperApp):
    """
    Add the key endpoints to the FastAPI app.

    :param app: SuperDuperApp
    """

    @app.add('/spec/show', method='get')
    def spec_show():
        return API_SCHEMAS

    @app.add('/spec/lookup', method='get')
    def spec_lookup():
        return MODULE_LOOKUP

    @app.add('/db/artifact_store/save_artifact', method='put')
    def db_artifact_store_save_artifact(datatype: str, raw: bytes = File(...)):
        r = app.db.artifact_store.save_artifact({'bytes': raw, 'datatype': datatype})
        return {'file_id': r['file_id']}

    @app.add('/db/artifact_store/get_artifact', method='get')
    def db_artifact_store_get_artifact(file_id: str, datatype: t.Optional[str] = None):
        bytes = app.db.artifact_store._load_bytes(file_id=file_id)

        if datatype is not None:
            datatype = app.db.datatypes[datatype]
        if datatype is None or datatype.media_type is None:
            media_type = magic.from_buffer(bytes, mime=True)
        else:
            media_type = datatype.media_type
        return Response(content=bytes, media_type=media_type)

    @app.add('/db/apply/stack', method='post')
    def db_apply_stack(info: t.Dict):
        if 'identifier' in info:
            component = Stack.from_list(
                content=info['_leaves'], db=app.db, identifier=info['identifier']
            )
        else:
            id = f'_component/{info["type_id"]}/{info["identifier"]}'
            r = {'_leaves': [{**info, 'id': id}], '_base': id}
            component = import_(r=r, db=app.db)
        app.db.apply(component)
        return {'status': 'ok'}

    @app.add('/db/apply/component', method='post')
    def db_apply_component(info: t.Dict):
        if '_leaves' in info:
            component = import_(r=info, db=app.db)
        else:
            id = f'_component/{info["type_id"]}/{info["dict"]["identifier"]}'
            r = {'_leaves': [{**info, 'id': id}], '_base': id}
            component = import_(r=r, db=app.db)
        app.db.apply(component)
        return {'status': 'ok'}

    @app.add('/db/remove', method='post')
    def db_remove(type_id: str, identifier: str):
        app.db.remove(type_id=type_id, identifier=identifier, force=True)
        return {'status': 'ok'}

    @app.add('/db/show', method='get')
    def db_show(
        type_id: t.Optional[str] = None,
        identifier: t.Optional[str] = None,
        version: t.Optional[int] = None,
    ):
        out = app.db.show(type_id=type_id, identifier=identifier, version=version)
        if isinstance(out, dict) and '_id' in out:
            del out['_id']
        if type_id == 'datatype' and identifier is None:
            out.extend(list(app.db.datatypes.keys()))
        return out

    @app.add('/db/metadata/show_jobs', method='get')
    def db_metadata_show_jobs(type_id: str, identifier: t.Optional[str] = None):
        return [
            r['job_id']
            for r in app.db.metadata.show_jobs(
                type_id=type_id, component_identifier=identifier
            )
            if 'job_id' in r
        ]

    @app.add('/db/execute', method='post')
    def db_execute(
        query: str = "<collection>.<method>(*args, **kwargs)",
        documents: t.List[t.Dict] = [],
    ):
        query = [x for x in query.split('\n') if x.strip()]
        query = parse_query(query, documents, db=app.db)

        logging.info('processing this query:')
        logging.info(query)

        result = app.db.execute(query)

        if isinstance(query, Insert) or isinstance(query, Delete):
            return {'_base': [str(x) for x in result[0]]}, []

        logging.warn(str(query))
        if isinstance(result, Document):
            result = [result]
        elif result is None:
            result = []
        else:
            result = list(result)
        for r in result:
            if '_id' in r:
                del r['_id']
        result = [strip_artifacts(r.encode()) for r in result]
        logging.warn(str(result))
        return result


build_app(app)
