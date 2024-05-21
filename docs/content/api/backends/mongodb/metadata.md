**`pinnacledb.backends.mongodb.metadata`** 

[Source code](https://github.com/SuperDuperDB/pinnacledb/blob/main/pinnacledb/backends/mongodb/metadata.py)

## `MongoMetaDataStore` 

```python
MongoMetaDataStore(self,
     conn: Any,
     name: Optional[str] = None) -> None
```
| Parameter | Description |
|-----------|-------------|
| conn | MongoDB client connection |
| name | Name of database to host filesystem |

Metadata store for MongoDB.

