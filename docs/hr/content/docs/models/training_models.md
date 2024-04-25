# Training models directly on your datastore

Similarly to [applying models to create predictions](./apply_models.md), training models is possible both procedurally and declaratively in `pinnacledb`.

When models are trained, if `CFG.cluster.dask_scheduler` has been configured (e.g. `dask://localhost:8786`), then `pinnacledb` deploys [a job on the configured `dask` cluster](../production/non_blocking_dask_jobs.md)

## Basic pattern

```python
db.add(
    <ModelCls>(
        *args, 
        trainer=Trainer(),
        **kwargs,
    )
)
```

## Fitting/ training models by framework

See the following links:

| Framework | Link |
| --- | --- |
| Scikit-Learn | [link](../ai_integrations/sklearn#training) |
| PyTorch | [link](../ai_integrations/pytorch#training) |
| Transformers | [link](../ai_integrations/transformers#training) |

<!-- ### Scikit-learn

See [here]

```python
from pinnacledb.ext.sklearn import Estimator
from sklearn.svm import SVC

m = Estimator(SVC(C=0.05))

m.fit(
    X='<input-col>',
    y='<target-col>',
    select=<query>,  # MongoDB, Ibis or SQL query
    db=db,
)
```

### Transformers

```python
from pinnacledb.ext.transformers import Pipeline
from pinnacledb import pinnacle

m = Pipeline(task='sentiment-analysis')

m.fit(
    X='<input-col>',
    y='<target-col>',
    db=db,
    select=<query>,   # MongoDB, Ibis or SQL query
    dataloader_num_workers=4,   # **kwargs are passed to `transformers.TrainingArguments`
)
```

### PyTorch

```python
import torch
from pinnacledb.ext.torch import Module

model = Module(
    'my-classifier',
    preprocess=lambda x: torch.tensor(x),
    object=torch.nn.Linear(64, 512),
    postprocess=lambda x: x.topk(1)[0].item(),
)

model.fit(
    X='<input>',
    db=db,
    select=<query>,  # MongoDB, Ibis or SQL query
    batch_size=100,  # any **kwargs supported by `pinnacledb.ext.torch.TorchTrainerConfiguration`
    num_workers=4,
)
``` -->