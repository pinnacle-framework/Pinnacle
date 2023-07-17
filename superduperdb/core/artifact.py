import typing as t
import uuid

from pinnacledb.datalayer.base.artifacts import ArtifactStore
from pinnacledb.misc.serialization import serializers


class ArtifactSavingError(Exception):
    pass


class Artifact:
    def __init__(
        self,
        artifact: t.Any = None,
        serializer: str = 'dill',
        info: t.Optional[t.Dict] = None,
        file_id: t.Any = None,
    ):
        self.serializer = serializer
        self.artifact = artifact
        self.info = info
        self.file_id = file_id

    def __repr__(self):
        return f'<Artifact artifact={str(self.artifact)} serializer={self.serializer}>'

    def serialize(self):
        serializer = serializers[self.serializer]
        if self.info is not None:
            bytes = serializer.encode(self.artifact, self.info)
        else:
            bytes = serializer.encode(self.artifact)
        return bytes

    def save(
        self, cache, artifact_store: t.Optional[ArtifactStore] = None, replace=False
    ):
        object_id = id(self.artifact)
        if object_id not in cache:
            bytes = self.serialize()
            file_id, sha1 = artifact_store.create_artifact(bytes=bytes)
            if replace and self.file_id is not None:
                artifact_store.delete_artifact(self.file_id)
            elif not replace and self.file_id is not None:
                raise ArtifactSavingError(
                    "Something has gone wrong in saving, "
                    f"Artifact {self.artifact} was already saved."
                )
            self.file_id = file_id
            details = {
                'file_id': file_id,
                'sha1': sha1,
                'id': object_id,
                'serializer': self.serializer,
                'info': self.info,
            }
            cache[object_id] = details
        return cache[id(self.artifact)]

    @staticmethod
    def load(r, artifact_store: ArtifactStore, cache):
        if r['file_id'] in cache:
            return cache[r['file_id']]
        artifact = artifact_store.load_artifact(
            r['file_id'], r['serializer'], info=r['info']
        )
        a = Artifact(
            artifact=artifact,
            serializer=r['serializer'],
            info=r['info'],
        )
        cache[r['file_id']] = a.artifact
        return a


class InMemoryArtifacts:
    def __init__(self):
        self.cache = {}

    def create_artifact(self, bytes):
        file_id = str(uuid.uuid4())
        self.cache[file_id] = bytes
        return file_id, ''

    def delete_artifact(self, file_id):
        del self.cache[file_id]
