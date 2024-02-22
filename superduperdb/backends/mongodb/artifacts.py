import click
import gridfs

from pinnacledb import logging
from pinnacledb.backends.base.artifact import ArtifactStore
from pinnacledb.misc.colors import Colors


class MongoArtifactStore(ArtifactStore):
    """
    Artifact store for MongoDB.

    :param conn: MongoDB client connection
    :param name: Name of database to host filesystem
    """

    def __init__(self, conn, name: str):
        super().__init__(name=name, conn=conn)
        self.db = self.conn[self.name]
        self.filesystem = gridfs.GridFS(self.db)

    def url(self):
        return self.conn.HOST + ':' + str(self.conn.PORT) + '/' + self.name

    def drop(self, force: bool = False):
        if not force:
            if not click.confirm(
                f'{Colors.RED}[!!!WARNING USE WITH CAUTION AS YOU '
                f'WILL LOSE ALL DATA!!!]{Colors.RESET} '
                'Are you sure you want to drop all artifacts? ',
                default=False,
            ):
                logging.warn('Aborting...')
        return self.db.client.drop_database(self.db.name)

    def _exists(self, file_id):
        return self.filesystem.find_one({'filename': file_id}) is not None

    def _delete_bytes(self, file_id: str):
        r = self.filesystem.find_one({'filename': file_id})
        if r is None:
            raise FileNotFoundError(f'No such file on GridFS {file_id}')
        return self.filesystem.delete(r._id)

    def _load_bytes(self, file_id: str):
        cur = self.filesystem.find_one({'filename': file_id})
        if cur is None:
            raise FileNotFoundError(f'File not found in {file_id}')
        return cur.read()

    def _save_bytes(self, serialized: bytes, file_id: str):
        return self.filesystem.put(serialized, filename=file_id)

    def disconnect(self):
        """
        Disconnect the client
        """

        # TODO: implement me
