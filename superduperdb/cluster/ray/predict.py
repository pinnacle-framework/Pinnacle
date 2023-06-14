import inspect
import os
from starlette.requests import Request
from ray import serve
from bson import BSON

from pinnacledb.datalayer.base.imports import get_database_from_database_type
from pinnacledb.core.documents import Document


@serve.deployment(
    route_prefix=f'/predict/{os.environ.get("pinnacleDB_MODEL", "ERROR")}',
    num_replicas=int(os.environ.get("pinnacleDB_NUM_REPLICAS", "1")),
)
class Server:
    def __init__(self):
        database_type = os.environ['pinnacleDB_DATABASE_TYPE']
        database_name = os.environ['pinnacleDB_DATABASE_NAME']
        self.db = get_database_from_database_type(database_type, database_name)
        print(self.db.models[os.environ['pinnacleDB_MODEL']])
        self.sig = inspect.signature(self.db.predict_one)

    async def __call__(self, http_request: Request) -> str:
        data = await http_request.body()
        data = BSON.decode(data)
        print(data)
        data = [Document.decode(r, types=self.db.types) for r in data]

        input_ = Document.decode(data['input_'], types=self.db.types)
        result = self.db.predict(os.environ['pinnacleDB_MODEL'], input_)
        return BSON.encode({'output': result.encode()})


server = Server.bind()
