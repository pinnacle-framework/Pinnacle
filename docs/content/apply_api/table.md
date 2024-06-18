# `Table`

- Use a table in your databackend database, which optionally has a `Schema` attached
- Table can be a `MongoDB` collection or an SQL table.

***Dependencies***

- [`Schema`](./schema.md)

***Usage pattern***

(Learn how to build a `Schema` [here](schema))

```python
from pinnacledb.backends.ibis import Table

table = Table(
    'my-table',
    schema=my_schema
)

db.apply(table)
```

In MongoDB, the attached `schema` will be used as the default `Schema` for that `Table` (collection).