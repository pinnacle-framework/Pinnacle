---
sidebar_position: 29
---

# Developer vs. production mode

SuperDuperDB may be run in 2 modes:

- **Developer** mode
- **Production** mode

These may be configured with `pinnacledb.CFG`.
By default `pinnacledb` runs in developer mode.
In developer mode, all instructions run in the foreground,
and calls to vector-search happen *in process*.

To set production mode, configure:

```python
from pinnacledb import CFG

s.CFG.mode = 'production'
```

With production mode configured, the system assumes the existence of:

- A [distributed **Dask** cluster](31_non_blocking_dask_jobs.md), with scheduler and workers configured to work with `pinnacledb`
- A [**change-data-capture** service](32_change_data_capture.md)
- A [**vector-search** service](33_vector_comparison_service.md), which finds similar vectors, given an input vector