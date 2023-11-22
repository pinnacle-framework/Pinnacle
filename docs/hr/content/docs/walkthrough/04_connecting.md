---
sidebar_position: 4
tags:
  - quickstart
---

# Connect your database

Now that you have configured `pinnacledb` with either `pinnacledb.CFG` or environment variables (see [here](../Getting%20Started/03_configuration.md)),
you are ready to connect to your database.

:::info
In this document we instantiate the variable `db` based on configuration and overrides.
In the remainder of the documentation, we reuse this variable without comment
:::

The simplest way to do this is with:

```python
from pinnacledb import pinnacle
db = pinnacle()
```

This command uses settings inherited from the configurations set previously.
In order to connect to a different database, one can do:

```python
db = pinnacle('mongodb://localhost:27018')
```

Additional configurations can be injected with `**kwargs`

```python
db = pinnacle('mongodb://localhost:27018', artifact_store='filesystem://./data')
```

... or by passing a modified `CFG` object.

```python
from pinnacledb import CFG

CFG.artifact_store = 'filesystem://./data'
db = pinnacle('mongodb://localhost:27018', CFG=CFG)
```

The `db` object is an instance of `pinnacledb.base.datalayer.Datalayer`.
The `Datalayer` class handles AI models and communicates with the databackend and associated components. Read more [here](../Fundamentals/07_datalayer_overview.md).