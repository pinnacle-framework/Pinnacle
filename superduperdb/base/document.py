import typing as t

from bson.objectid import ObjectId

from pinnacledb.base.code import Code
from pinnacledb.base.leaf import Leaf, _import_item
from pinnacledb.components.component import Component
from pinnacledb.components.datatype import (
    _ENCODABLES,
    Encodable,
    _BaseEncodable,
)
from pinnacledb.misc.special_dicts import MongoStyleDict, SuperDuperFlatEncode
from pinnacledb.components.schema import Schema

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer


 

ContentType = t.Union[t.Dict, Encodable]
ItemType = t.Union[t.Dict[str, t.Any], Encodable, ObjectId]

_LEAF_TYPES = {
    'component': Component,
    'leaf': Leaf,
    'remote_code': Code,
}
_LEAF_TYPES.update(_ENCODABLES)
_OUTPUTS_KEY = '_outputs'

def get_schema(db, schema: t.Union['Schema', str]) -> 'Schema':
    """Handle schema caching and loading."""
    if isinstance(schema, Schema):
        return schema
    assert isinstance(schema, str)
    if db is None:
        raise ValueError(f'A Datalayer instance is required for encoding with schema {schema}')

    return db.schemas[schema]


class Document(MongoStyleDict):
    """A wrapper around an instance of dict or a Encodable.

    The document data is used to dump that resource to a mix of json-able content, ids and `bytes`

    """

    _DEFAULT_ID_KEY: str = '_id'

    def __init__(
        self,
        *args,
        schema: t.Optional['Schema'] = None,
        db: t.Optional['Datalayer'] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.db = db

    def _deep_flat_encode(
        self,
        cache,
        blobs,
        files,
        leaves_to_keep: t.Sequence = (),
        schema: t.Optional['Schema'] = None,
    ):
        out = dict(self)
        if schema is not None:
            out = schema.deep_flat_encode_data(
                self,
                cache,
                blobs,
                files,
                leaves_to_keep=leaves_to_keep,
            )
        return _deep_flat_encode(
            out,
            cache,
            blobs,
            files,
            leaves_to_keep=leaves_to_keep,
            schema=schema
        )

    def encode(
        self, schema: t.Optional[t.Union['Schema', str]] = None, leaves_to_keep: t.Sequence = ()
    ) -> t.Dict:
        cache = {}
        blobs = {}
        files = {}
            
        # Get schema from database.
        schema = get_schema(self.db, schema) if schema else None

        out = self._deep_flat_encode(
            cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=schema
        )

        out['_leaves'] = cache
        out['_files'] = files
        out['_blobs'] = blobs
        out = SuperDuperFlatEncode(out)
        return out

    @classmethod
    def decode(
        cls, r, schema: t.Optional['Schema'] = None, db: t.Optional['Datalayer'] = None
    ):
        cache = {}
        blobs = {}
        files = {}

        if '_leaves' in r:
            cache = r['_leaves']
            del r['_leaves']

        if '_blobs' in r:
            blobs = r['_blobs']
            del r['_blobs']

        if '_files' in r:
            files = r['_files']
            del r['_files']

        if schema is not None:
            r = schema.decode_data(r)
        r = _deep_flat_decode(r, cache, blobs, files=files, db=db)

        if isinstance(r, dict):
            return Document(r, schema=schema)
        else:
            return r

    @property
    def variables(self) -> t.List[str]:
        """Return a list of variables in the object."""
        from pinnacledb.base.variables import _find_variables

        return _find_variables(self)

    def set_variables(self, db, **kwargs) -> 'Document':
        """Set free variables of self.

        :param db: The datalayer to use.
        """
        from pinnacledb.base.variables import _replace_variables

        content = _replace_variables(
            self, db, **kwargs
        )  # replace variables with values
        return Document(**content)

    def __repr__(self) -> str:
        return f'Document({repr(dict(self))})'

    def unpack(self, leaves_to_keep: t.Sequence = ()) -> t.Any:
        """Returns the content, but with any encodables replaced by their contents.

        :param db: The datalayer to use.
        :param leaves_to_keep: The types of leaves to keep.
        """
        out = _unpack(self, leaves_to_keep=leaves_to_keep)
        if '_base' in out:
            out = out['_base']
        return out


class QueryUpdateDocument(Document):
    @classmethod
    def from_document(cls, document):
        r = dict(document)
        r = r.get('$set', r)
        return QueryUpdateDocument(r)

    @staticmethod
    def _create_metadata_update(update, original=None):
        # Update leaves
        if original is None:
            original = update
        metadata = original.pop('_leaves', {})
        for m, v in metadata.items():
            update[f'_leaves.{m}'] = v

        # Append files and blobs
        push = {}
        for k in ('_files', '_blobs'):
            item = original.pop(k, [])
            if item:
                push[k] = {k: {'$each': item}}
        update = {'$set': update, '$push': push}
        return update

    def encode(
        self,
        original: t.Any = None,
        schema: t.Optional['Schema'] = None,
        leaves_to_keep: t.Sequence = (),
    ) -> t.Dict:
        r = dict(self)
        r = r.get('$set', r)
        update = super().encode(schema=schema, leaves_to_keep=leaves_to_keep)
        return self._create_metadata_update(update, original=original)


def _unpack(item: t.Any, db=None, leaves_to_keep: t.Sequence = ()) -> t.Any:
    if isinstance(item, _BaseEncodable) and not any([isinstance(item, l) for l in leaves_to_keep]):  # type: ignore[arg-type]
        return item.unpack()
    elif isinstance(item, dict):
        return {k: _unpack(v, leaves_to_keep=leaves_to_keep) for k, v in item.items()}
    elif isinstance(item, list):
        return [_unpack(x, leaves_to_keep=leaves_to_keep) for x in item]
    else:
        return item


def _deep_flat_encode(r, cache, blobs, files, leaves_to_keep: t.Sequence[Leaf] = (), schema: t.Optional[Schema] = None):
    if isinstance(r, dict):
        return {
            k: _deep_flat_encode(v, cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=schema)
            for k, v in r.items()
        }
    if isinstance(r, list):
        return [
            _deep_flat_encode(x, cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=schema)
            for x in r
        ]
    if isinstance(r, Leaf):
        return r._deep_flat_encode(cache, blobs, files, leaves_to_keep=leaves_to_keep, schema=schema)
    return r


def _get_leaf_from_cache(k, cache, blobs, files, db: t.Optional['Datalayer'] = None):
    if isinstance(cache[k], Leaf):
        leaf = cache[k]
        if isinstance(leaf, Leaf):
            leaf.db = db
        return leaf
    leaf = _deep_flat_decode(cache[k], cache, blobs, files, db=db)
    cache[k] = leaf
    if isinstance(leaf, Leaf):
        leaf.db = db
    return leaf


def _deep_flat_decode(r, cache, blobs,files={}, db: t.Optional['Datalayer'] = None):
    # TODO: Document this function (Important)
    if isinstance(r, Leaf):
        r.db = db
        return r
    if isinstance(r, list):
        return [_deep_flat_decode(x, cache, blobs, files=files, db=db) for x in r]
    if isinstance(r, dict) and '_path' in r:
        parts = r['_path'].split('/')
        cls = parts[-1]
        module = '.'.join(parts[:-1])
        dict_ = {k: v for k, v in r.items() if k != '_path'}
        dict_ = _deep_flat_decode(dict_, cache, blobs, files, db=db)
        return _import_item(cls=cls, module=module, dict=dict_, db=db)
    if isinstance(r, dict):
        return {k: _deep_flat_decode(v, cache, blobs, files, db=db) for k, v in r.items()}
    if isinstance(r, str) and r.startswith('?'):
        return _get_leaf_from_cache(r[1:], cache, blobs, files, db=db)
    if isinstance(r, str) and r.startswith('%'):
        uuid = r.split('/')[-1]
        return db.load(uuid=uuid)
    return r
