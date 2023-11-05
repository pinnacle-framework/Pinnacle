---
sidebar_position: 13
---

# SQL Query API

## Setup

The first step in working with an SQL table, is to define a table and schema

```python
from pinnacledb.backends.ibis import dtype, Table
from pinnacledb import Encoder, Schema

my_enc = Encoder('my-enc')

schema = Schema('my-schema', fields={'img': my_enc, 'text': dtype('str'), 'rating': dtype('int')})

db = pinnacle()

t = Table('my-table', schema=schema)

db.add(t)
```

## Inserting data

Table data must correspond to the `Schema` for that table:

```python
import pandas

pandas.DataFrame([
    PIL.Image.open('image.jpg'), 'some text', 4,
    PIL.Image.open('other_image.jpg'), 'some other text', 3,
])

t.insert(dataframe)
```

## Selecting data

`pinnacledb` supports selecting data via the `ibis` query API.

The following are equivalent:

```python
db.execute(
    t.filter(t.rating > 3).limit(5).select(t.image)
)
```

### Vector-search

Vector-searches are supported via the `like` operator:

```python
db.execute(
    t.like({'text': 'something like this'}, vector_index='my-index')
     .filter(t.rating > 3)
     .limit(5)
     .select(t.image, t.id)
)
```

Vector-searches are either first or last in a chain of operations:

```python
db.execute(
    t.filter(t.rating > 3)
     .limit(5)
     .select(t.image, t.id)
     .like({'text': 'something like this'}, vector_index='my-index')
)
```

### Coming soon: support for raw-sql

... the first query above will be equivalent to:

```python
db.execute(
    'SELECT img FROM my-table WHERE rating > 3 LIMIT 5;'
)
```

... the second will be equivalent to:

```python
db.execute(
    '''
    SELECT img FROM my-table 
    LIKE text = 'something like this'
    WHERE rating > 3
    LIMIT 5;
    '''
)
```

## Updating data

Updates are not covered for `pinnacledb` SQL integrations.

## Deleting data

```python
db.databackend.drop_table('my-table')
```