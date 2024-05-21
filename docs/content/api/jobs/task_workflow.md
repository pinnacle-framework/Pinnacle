**`pinnacledb.jobs.task_workflow`** 

[Source code](https://github.com/SuperDuperDB/pinnacledb/blob/main/pinnacledb/jobs/task_workflow.py)

## `TaskWorkflow` 

```python
TaskWorkflow(self,
     database: 'Datalayer',
     G: 'DiGraph' = <factory>) -> None
```
| Parameter | Description |
|-----------|-------------|
| database | ``DB`` instance to use |
| G | ``networkx.DiGraph`` to use as the graph |

Task workflow class.

Keep a graph of jobs that need to be performed and their dependencies,
and perform them when called.

