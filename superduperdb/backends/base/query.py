import dataclasses as dc
import json
import re
import typing as t
import uuid
from abc import ABC, abstractmethod
from functools import wraps

from pinnacledb.base.document import Document
from pinnacledb.base.leaf import Leaf
from pinnacledb.misc.hash import hash_string

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer
    from pinnacledb.components.schema import Schema


def applies_to(*flavours):
    def decorator(f):
        @wraps(f)
        def decorated(self, *args, **kwargs):
            msg = (
                f'Query {self} does not match any of accepted patterns {flavours},'
                f' for the {f.__name__} method to which this method applies.'
            )

            try:
                flavour = self.flavour
            except TypeError:
                raise TypeError(msg)
            assert flavour in flavours, msg
            return f(self, *args, **kwargs)

        return decorated

    return decorator


@dc.dataclass(kw_only=True, repr=False)
class Query(Leaf, ABC):
    flavours: t.ClassVar[t.Dict[str, str]] = {}
    parts: t.Sequence[t.Union[t.Tuple, str]] = ()

    def __getitem__(self, item):
        if not isinstance(item, slice):
            return super().__getitem__(item)
        assert isinstance(item, slice)
        parts = self.parts[item]
        return type(self)(db=self.db, identifier=self.identifier, parts=parts)

    def set_db(self, db):
        def _set_db(r, db):
            if isinstance(r, (tuple, list)):
                out = [_set_db(x, db) for x in r]
                return out
            if isinstance(r, dict):
                return {k: _set_db(v, db) for k, v in r.items()}
            if isinstance(r, Query):
                r.db = db
                return r

            return r

        self.db = db

        # Recursively set db
        parts = []
        for part in self.parts:
            if isinstance(part, str):
                parts.append(part)
                continue
            part_args = tuple(_set_db(part[1], db))
            part_kwargs = _set_db(part[2], db)
            part = part[0]
            parts.append((part, part_args, part_kwargs))
        self.parts = parts

    def _get_flavour(self):
        _query_str = self._to_str()
        repr_ = _query_str[0]

        if repr_ == self.identifier and not (_query_str[0] and _query_str[-1]):
            # Table selection query.
            return 'select'

        try:
            return next(k for k, v in self.flavours.items() if re.match(v, repr_))
        except StopIteration:
            raise TypeError(
                f'Query flavour {repr_} did not match existing {type(self)} flavours'
            )

    def _get_parent(self):
        return self.db.databackend.get_table_or_collection(self.identifier)

    @property
    def flavour(self):
        return self._get_flavour()

    @property
    @abstractmethod
    def documents(self):
        pass

    @property
    @abstractmethod
    def type(self):
        pass

    @property
    def _id(self):
        return f'query/{hash_string(str(self))}'

    def _deep_flat_encode(
        self,
        cache,
        blobs,
        files,
        leaves_to_keep=(),
        schema: t.Optional['Schema'] = None,
    ):
        query, documents = self._dump_query()
        documents = [Document(r) for r in documents]
        for i, doc in enumerate(documents):
            documents[i] = doc._deep_flat_encode(
                cache, blobs, files, leaves_to_keep, schema=schema
            )
        cache[self._id] = {
            '_path': 'pinnacledb/backends/base/query/parse_query',
            'documents': documents,
            'query': query,
        }
        return f'?{self._id}'

    @staticmethod
    def _update_item(a, documents, queries):
        if isinstance(a, Query):
            a, sub_documents, sub_queries = a._to_str()
            documents.update(sub_documents)
            queries.update(sub_queries)
            id_ = uuid.uuid4().hex[:5].upper()
            queries[id_] = a
            arg = f'query[{id_}]'
        else:
            id_ = uuid.uuid4().hex[:5].upper()
            if isinstance(a, dict):
                documents[id_] = a
                arg = f'documents[{id_}]'
            elif isinstance(a, list):
                documents[id_] = {'_base': a}
                arg = f'documents[{id_}]'
            else:
                try:
                    arg = json.dumps(a)
                except Exception:
                    documents[id_] = {'_base': a}
                    arg = id_
        return arg

    def _to_str(self):
        documents = {}
        queries = {}
        #out = self.identifier[:]
        out = str(self.identifier)
        for part in self.parts:
            if isinstance(part, str):
                out += f'.{part}'
                continue
            args = []
            for a in part[1]:
                args.append(self._update_item(a, documents, queries))
            args = ', '.join(args)
            kwargs = {}
            for k, v in part[2].items():
                kwargs[k] = self._update_item(v, documents, queries)
            kwargs = ', '.join([f'{k}={v}' for k, v in kwargs.items()])
            if part[1] and part[2]:
                out += f'.{part[0]}({args}, {kwargs})'
            if not part[1] and part[2]:
                out += f'.{part[0]}({kwargs})'
            if part[1] and not part[2]:
                out += f'.{part[0]}({args})'
            if not part[1] and not part[2]:
                out += f'.{part[0]}()'
        return out, documents, queries

    def _dump_query(self):
        output, documents, queries = self._to_str()
        if queries:
            output = '\n'.join(list(queries.values())) + '\n' + output
        for i, k in enumerate(queries):
            output = output.replace(k, str(i))
        for i, k in enumerate(documents):
            output = output.replace(k, str(i))
        documents = list(documents.values())
        return output, documents

    def __repr__(self):
        output, docs = self._dump_query()
        for i, doc in enumerate(docs):
            doc_string = str(doc)
            if isinstance(doc, Document):
                doc_string = str(doc.unpack())
            output = output.replace(f'documents[{i}]', doc_string)
        return output

    def __eq__(self, other):
        return type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=self.parts + [('__eq__', (other,), {})],
        )

    def __leq__(self, other):
        return type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=self.parts + [('__leq__', (other,), {})],
        )

    def __geq__(self, other):
        return type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=self.parts + [('__geq__', other)],
        )

    def __getattr__(self, item):
        return type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=[*self.parts, item],
        )

    def __call__(self, *args, **kwargs):
        assert isinstance(self.parts[-1], str)
        return type(self)(
            db=self.db,
            identifier=self.identifier,
            parts=[*self.parts[:-1], (self.parts[-1], args, kwargs)],
        )

    def _encode_or_unpack_args(self, r, db, method='encode', parent=None):
        if isinstance(r, Document):
            return getattr(r, method)()
        if isinstance(r, (tuple, list)):
            out = [
                self._encode_or_unpack_args(x, db, method=method, parent=parent)
                for x in r
            ]
            if isinstance(r, tuple):
                return tuple(out)
            return out
        if isinstance(r, dict):
            return {
                k: self._encode_or_unpack_args(v, db, method=method, parent=parent)
                for k, v in r.items()
            }
        if isinstance(r, Query):
            parent = super(type(self), r)._get_parent()
            return super(type(self), r)._execute(parent)

        return r

    def _execute(self, parent, method='encode'):
        for part in self.parts:
            if isinstance(part, str):
                parent = getattr(parent, part)
                continue
            args = self._encode_or_unpack_args(
                part[1], self.db, method=method, parent=parent
            )
            kwargs = self._encode_or_unpack_args(
                part[2], self.db, method=method, parent=parent
            )
            parent = getattr(parent, part[0])(*args, **kwargs)
        return parent

    @abstractmethod
    def _create_table_if_not_exists(self):
        pass

    def execute(self, db=None):
        self.db = db or self.db
        assert self.db is not None, 'No datalayer (db) provided'
        self._create_table_if_not_exists()
        parent = self._get_parent()
        try:
            flavour = self._get_flavour()
            handler = f'_execute_{flavour}' in dir(self)
            if handler is False:
                raise AssertionError
            handler = getattr(self, f'_execute_{flavour}')
            return handler(parent=parent)
        except TypeError as e:
            if 'did not match' in str(e):
                return self._execute(parent=parent)
        except AssertionError:
            return self._execute(parent=parent)

    @property
    @abstractmethod
    def primary_id(self):
        pass

    @abstractmethod
    def model_update(
        self,
        ids: t.List[t.Any],
        predict_id: str,
        outputs: t.Sequence[t.Any],
        flatten: bool = False,
        **kwargs,
    ):
        pass

    @abstractmethod
    def add_fold(self, fold: str):
        pass

    @abstractmethod
    def select_using_ids(self, ids: t.Sequence[str]):
        pass

    @property
    @abstractmethod
    def select_ids(self, ids: t.Sequence[str]):
        pass

    @abstractmethod
    def select_ids_of_missing_outputs(self, predict_id: str):
        pass

    @abstractmethod
    def select_single_id(self, id: str):
        pass

    @property
    @abstractmethod
    def select_table(self):
        pass


def _parse_query_part(part, documents, query, builder_cls):
    current = builder_cls(identifier=part.split('.')[0], parts=())
    part = part.split('.')[1:]
    for comp in part:
        match = re.match('^([a-zA-Z0-9_]+)\((.*)\)$', comp)
        if match is None:
            current = getattr(current, comp)
            continue
        if not match.groups()[1].strip():
            current = getattr(current, match.groups()[0])()
            continue

        comp = getattr(current, match.groups()[0])
        args_kwargs = [x.strip() for x in match.groups()[1].split(',')]
        args = []
        kwargs = {}
        for x in args_kwargs:
            if '=' in x:
                k, v = x.split('=')
                kwargs[k] = eval(v, {'documents': documents, 'query': query})
            else:
                args.append(eval(x, {'documents': documents, 'query': query}))
        current = comp(*args, **kwargs)
    return current


def parse_query(
    query: t.Union[str, list],
    documents,
    builder_cls,
    db: t.Optional['Datalayer'] = None,
):
    documents = [Document(r) for r in documents]
    if isinstance(query, str):
        query = [x.strip() for x in query.split('\n') if x.strip()]
    for i, q in enumerate(query):
        query[i] = _parse_query_part(q, documents, query[:i], builder_cls)
    return query[-1]


class Model(Query):
    ...
