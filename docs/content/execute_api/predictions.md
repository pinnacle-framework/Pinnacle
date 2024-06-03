# Predictions

Model predictions may be deployed by calling `Model.predict` or `Model.predict_one` directly.

```python
m = db.load('model', 'my-model')

# *args, **kwargs depend on model implementation
results = m.predict_one(*args, **kwargs)
```

An alternative is to construct a prediction "query" as follows:

```python
# *args, **kwargs depend on model implementation
db['my-model'].predict_one(*args, **kwargs).execute()
```

The results should be the same for both versions.