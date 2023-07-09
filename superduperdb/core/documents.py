from pinnacledb.core.base import Artifact
from pinnacledb.core.encoder import Encodable
from pinnacledb.datalayer.base.artifacts import ArtifactStore
from pinnacledb.misc.uri_cache import Cached
import typing as t

ContentType = t.Union[t.Dict, Encodable]


class ArtifactDocument:
    def __init__(self, content):
        self.content = content

    def load_artifacts(self, artifact_store: ArtifactStore, cache: t.Dict):
        return self._load_artifacts(self.content, artifact_store, cache)

    @staticmethod
    def _load_artifacts(d: t.Any, artifact_store: ArtifactStore, cache: t.Dict):
        if isinstance(d, dict):
            if 'file_id' in d and 'serializer' in d:
                return Artifact.load(d, artifact_store, cache)
            else:
                for k, v in d.items():
                    if isinstance(v, dict) or isinstance(v, list):
                        d[k] = ArtifactDocument._load_artifacts(
                            v, artifact_store, cache
                        )
        if isinstance(d, list):
            for i, x in enumerate(d):
                d[i] = ArtifactDocument._load_artifacts(x, artifact_store, cache)
        return d

    @staticmethod
    def _save_artifacts(
        d: t.Any,
        artifact_store: ArtifactStore,
        cache: t.Dict,
        replace: bool = False,
    ):
        if isinstance(d, dict):
            keys = list(d.keys())
            for k in keys:
                v = d[k]
                if isinstance(v, dict) or isinstance(v, list):
                    ArtifactDocument._save_artifacts(v, artifact_store, cache)
                if isinstance(v, Artifact):
                    v.save(
                        artifact_store=artifact_store,
                        cache=cache,
                        replace=replace,
                    )
                    d[k] = cache[id(v._artifact)]
        if isinstance(d, list):
            for i, x in enumerate(d):
                if isinstance(x, Artifact):
                    x.save(
                        artifact_store=artifact_store,
                        cache=cache,
                    )
                    d[i] = cache[id(x._artifact)]
                ArtifactDocument._save_artifacts(x, artifact_store, cache)

    def save_artifacts(
        self, artifact_store: ArtifactStore, cache: t.Dict, replace: bool = False
    ):
        return self._save_artifacts(
            self.content, artifact_store, cache, replace=replace
        )


class Document(Cached[ContentType]):
    """
    A wrapper around an instance of dict or a Encodable which may be used to dump
    that resource to a mix of jsonable content or `bytes`
    """

    content: t.Dict

    def __hash__(self):
        return super().__hash__()

    def _encode(self, r: t.Any):
        if isinstance(r, dict):
            return {k: self._encode(v) for k, v in r.items()}
        elif isinstance(r, Encodable):
            return r.encode()
        return r

    def encode(self):
        return self._encode(self.content)

    @classmethod
    def decode(cls, r: t.Dict, types: t.Dict):
        if isinstance(r, Document):
            return Document(cls._decode(r, types))
        elif isinstance(r, dict):
            return cls._decode(r, types)
        raise NotImplementedError(f'type {type(r)} is not supported')

    @classmethod
    def _decode(cls, r: t.Dict, types: t.Dict):
        if isinstance(r, dict) and '_content' in r:
            type = types[r['_content']['type']]
            try:
                return type.decode(r['_content']['bytes'])
            except KeyError:
                return r
        elif isinstance(r, list):
            return [cls._decode(x, types) for x in r]
        elif isinstance(r, dict):
            for k in r:
                r[k] = cls._decode(r[k], types)
        return r

    def __getitem__(self, item: str):
        assert isinstance(self.content, dict)
        return self.content[item]

    def __setitem__(self, key: str, value: t.Any):
        assert isinstance(self.content, dict)
        self.content[key] = value

    @classmethod
    def _unpack_datavars(cls, item: t.Any):
        if isinstance(item, Encodable):
            return item.x
        elif isinstance(item, dict):
            return {k: cls._unpack_datavars(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [cls._unpack_datavars(x) for x in item]
        else:
            return item

    def unpack(self):
        return self._unpack_datavars(self.content)
