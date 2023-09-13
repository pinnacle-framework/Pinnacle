---
sidebar_position: 2
---

# Configuration

SuperDuperDB ships with configuration via `pydantic`. Read more about `pydantic` [here](https://docs.pydantic.dev/latest/). Using `pydantic`, SuperDuperDB comes with a full set of defaults in `pinnacledb.base.config.py`.

These configurations may be overridden, prior to invoking SuperDuperDB classes or by setting environment 
variables prior to starting the session:

- import `pinnacledb.CFG` and overwriting values in that object
- environment variable `pinnacleB_...`
- by a file `configs.json` in the
working directory.

Here are the key configuration settings:

| setting                | meaning                | example                                |
| ---                    | ---                    | ---                                    |
| `CFG.data_backend`     | URI for data-store     | `'mongodb://localhost:27017/my_db'`    |
| `CFG.artifact_store`   | URI for artifact-store | `'s3://pinnacledb-artifacts'`        |
| `CFG.metadata_store`   | URI for meta-data      | `'mongodb://localhost:27017/metadata'` |
| `CFG.vector_search`    | URI for vector-search  | `'mongodb://localhost:27017/my_db'`    |