---
sidebar_position: 31
---

# Running non-blocking dask computations in the background

`pinnacledb` offers the possiblity to run all long running blocking jobs in the background via `dask`.
Read about the `dask` project [here](https://www.dask.org/).

To configure this feature, configure:

```python
from pinnacledb import CFG

CFG.mode = 'production'
```

When this is so-configured the following functions push their computations to the `dask` cluster:

- `db.add`
- `db.insert`
- `db.update`
- `Model.predict`
- `Model.fit`

When `dask` is configured, these functions returns either a `pinnacledb.job.Job` object, or an iterable thereof.

```python
job = m.predict(     # a `pinnacle.job.ComponentJob` object
    X='x',
    db=db,
    select=Collection('localcluster').find(),
)

job.watch()          # watch the `stdout` of the `Job`
```