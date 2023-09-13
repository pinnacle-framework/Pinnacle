---
sidebar_position: 4
---

# Queries

:::info
SuperDuperDB wraps standard datastore query APIs. It augments
these queries with support for vector-search and recall of complex data-types.
:::

SuperDuperDB queries are based on the queries of the underlying database, upon which the 
`DB` is based (see the [section on the `DB`](db)). 

Unlike some Python clients, in SuperDuperDB, queries are objects, rather then methods or functions.
This allows SuperDuperDB to serialize these queries for use in diverse tasks, such as model 
applications using the `Listener` paradigm (see [here](listeners)), model application, and management of vector-indices).

A query is executed as follows:

```python
# db a `DB` instance
db.execute(query)
```

## MongoDB

We currently provide first-class support for MongoDB as the database backend. As in `pymongo` all queries operate at the collection level:

```python
from pinnacledb.db.mongodb.query import Collection

collection = Collection(name='documents')
```

With this collection standard query types may be executed. Whereas `pymongo` returns vanilla python dictionaries, SuperDuperDB returns dictionaries wrapped as `Document` instances:


```python
db.execute(collection.find_one())
Document({'_id': ObjectId('64b89e92c08139e1cedc11a4'), 'x': Encodable(x=tensor([ 0.2059,  0.5608,  ...]), encoder=Encoder(identifier='torch.float32[512]', decoder=<Artifact artifact=<pinnacledb.encoders.torch.tensor.DecodeTensor object at 0x1785b5750> serializer=pickle>, encoder=<Artifact artifact=<pinnacledb.encoders.torch.tensor.EncodeTensor object at 0x1786767d0> serializer=pickle>, shape=[512], version=0)), '_fold': 'train'})
```

`Documents` are also used, whenever a query involves inserting data into the database. The reason for this, 
is that the data may contain complex data-types such as images (see [the section on encoders](encoders) for more detail):

```python
from pinnacledb.core.document import Document as D
db.execute(
    collection.insert_many([
        D({'this': f'is a test {i}'})
        for i in range(10)
    ])
)
```

SuperDuperDB also includes a composite API, enabling support for vector-search together with the query API of the database: see the [section on vector-search](/docs/docs/usage/vector_index) for details.

Supported MongoDB queries:

- `find_one`
- `find`
- `aggregate`
- `update_one`
- `update_many`
- `delete_many`

### Featurization

In some AI applications, for instance in [transfer learning](https://en.wikipedia.org/wiki/Transfer_learning), it is useful to "represent" data using some model-derived "features".
We support featurization in combination with `find` and `find_one` queries:

To do this, one chains these methods with `.featurize`, specifying the model with which one would like to featurize. In MongoDB this comes out as:

```python
cursor = db.execute(
    collection.find().featurize({'image': 'my_resnet_50'})
)
```

See the [model section](model) for information on how to compute and keep features (model outputs)
up to date.

### Vector Search queries

If one or more `VectorIndex` instances have been configured together with the `DB`, these 
may be used in hybrid queries together with standard databasing queries:

```python
cursor_1 = db.execute(
    collection.like({'image': my_image}), vector_index='<index>').find({'<key>': '<value>'})
cursor_2 = db.execute(
    collection.find({'<key>': '<value>'}).like({'image': my_image}, vector_index='<index>')
)
```

## SQL data-backends (experimental)

Using our integration via `ibis`, we support a number of SQL databases and more. See [here](db)
for more information.

Executing queries here is precisely analogous to vanilla `ibis` query application, 
with the addition that vector-search queries may be built on top.

As usual, the tables need to be set up with SuperDuperDB initiialy:

```python
from pinnacledb.db.ibis.query import Table
from sueprduperdb.db.ibis.schema import IbisSchema
from pinnacledb.db.ibis.field_types import dtype

schema = IbisSchema(
    identifier='my_schema',
    fields={
        'id': dtype('int64'),
        'this': dtype('str'),
        'label': dtype('int32'),
    },
)

table = Table('my-table', schema=schema)
t.create(db)
db.add(t)
```

Once setup, we can insert data:

```python
from pinnacledb.core.document import Document as D
db.execute(
    table.insert([
        D({'this': f'is a test {i}', 'label': random.randrange(2)})
        for i in range(10)
    ])
)
```

And also select data:

```python
db.execute(table.select('this').filter(table.label == 0))
```

If we've also added a [`VectorIndex`](/docs/docs/usage/vector_index), then 
we can use this in a hybrid SQL + vector-search query:

```python
db.execute(
    table
        .like({'this': 'is another test'}, vector_index='my-index')
        .select('this')
        .filter(table.label == 0)
)
```


