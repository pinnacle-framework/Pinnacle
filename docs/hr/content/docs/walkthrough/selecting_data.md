---
sidebar_position: 5
---

# Selecting data

After inserting data to `pinnacledb`, it may be queries with a `Select` query.

## MongoDB

MongoDB offers 2 types of basic `Select` query. All basic forms supported by the `pymongo` API are also supported.

### Find

```python
results = collection.find({}, {}).limit(20)      # type(results) == pinnacledb.base.cursor.SuperDuperCursor
for r in results:
    print(r)        # type(r) == Document
    print(r.unpack())       # type(r.unpack()) dict
```

### Aggregate

```python
results = collection.aggregate([
    {'$match': {}},
    {'$project': {'_id': 0}}
    ...
])
```

## SQL

Most `ibis` read-query types are supported. An important requirement, is that tables referred to have 
been [previously defined](./data_encodings_and_schemas.md) and loaded in order to create a query:

```python
t = db.load('table', 'my_table')
results = db.execute(t.select('audio').limit(20))        #   SuperDuperCursor
results = results.as_pandas()     # convert to pandas.DataFrame if desired
```