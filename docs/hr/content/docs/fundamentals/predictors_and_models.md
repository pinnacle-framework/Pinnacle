---
sidebar_position: 5
---

# Predictors and models

## Predictors

The base class which enables predictions in `pinnacledb` is the `Predictor` mixin class.

A `Predictor` is a class which implements the `.predict` method; this mimics `.predict` from 
[Scikit-Learn](https://scikit-learn.org/stable/) and related frameworks, but has support
for prediction directly via the `Datalayer`.

A typical call to `.predict` looks like this:

```python
predictor.predict(
    X='<key-column>'     # key of documents or column of table to take as input
    db=db                # `Datalayer` instance, built via `db = pinnacle()`
    select=my_select     # database query over which to compute outputs
    **predict_kwargs     # additional parameters for `.predict`
)
```

Examples of `Predictor` classes are the AI-API classes in

- `pinnacledb.ext.openai.OpenAI*`
- `pinnacledb.ext.anthropic.Anthropic*`
- `pinnacledb.ext.cohere.Cohere*`

## Models

A model is a particular type of `Predictor` which carries large chunks of data around
in order to implement predictions. These blobs can be, for example, the weights 
of a deep learning architecture or similar important data.

Examples of `Model` are:

- `pinnacledb.ext.torch.TorchModel`
- `pinnacledb.ext.sklearn.Estimator`
- `superdueprdb.ext.transformers.Pipeline`

Each of these inheriting classes also implements the `.fit` method, which re-parametrizes the class in question, 
typicall via a machine learning task and objective function.

A typical call to `.fit` looks like this:

```python
model.fit(
    X='<input-key-column>',    # key of documents or column of table to take as input
    y='<target-key>',          # key of documents or column of table to take as target of fitting
    db=db,                     # `Datalayer` instance, built via `db = pinnacle()`
    select=my_select,          # database query for training and validation data
    **fit_kwargs,              # additional parameters for .fit
)
```
