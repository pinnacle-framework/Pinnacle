---
sidebar_position: 3
---

# Models

```{note}
The SuperDuperDB `Model` wrapper is an extension of standard Python-AI-ecosystem models.
`Model` adds preprocessing, postprocessing, and communication with the `DB`
to the standard toolkit.
```

In SuperDuperDB, the primary mode to integrating a new AI model, framework or API provider
is via the `Model` abstraction. This maybe thought of in the following way:

- A wrapper around AI frameworks facilitating use of models with the database.
- A self contained unit of functionality handling all communication with the database.
- A unifying abstraction bringing all AI frameworks onto a single playing field.
- An trainable, parametrizable extension of UDFs from traditional databasing.

The uniformity of the abstraction is inspired by the Sklearn `.fit`, `.predict` paradigm,
but with additional features which are required in order to allow the models to read and
write to the database. We extend this paradigm to frameworks, which have taken their 
own path in API design, bringing all frameworks into a single world of terminology and
functionality.

## Supported frameworks

The following frameworks are supported natively by SuperDuperDB:

- `sklearn`
- `torch`
- `transformers`
- `openai`

The key class is located in `pinnacledb.ext.<framework>.<Framework>Model`:

- `pinnacledb.ext.sklearn.SklearnModel.`
- `pinnacledb.ext.torch.TorchModel.`
- `pinnacledb.ext.transformers.TransformersModel.`
- `pinnacledb.ext.openai.OpenAIModel.`

The wrappers from each framework include parameters fom the `Model` base class:

```python
from pinnacledb.core.model import Model

m = Model(
    object=<model>,    # object from one of the AI frameworks
    preprocess=<preprocess>,    # callable
    postprocess=<postprocess>,    # callable
    encoder=<encoder>,    # `Encoder` instance
)
```

See [below](model-design) for an explanation of each of these parameters.
Here are examples of each of these parameters in several frameworks and applications:

| Application | Task | Framework(s) | `object` | `preprocess`               | `postprocess` | `encoder` |
| ----------- | ----------- | ------------ | ------------------------ | ----------- | ------- | ----------- |
| Vision      | Classification | `torch`      | CNN | `torchvision.transforms` | Top-K estimate | `None` |
| Generative | Image generation | `torch` | GAN | `None` | `None` | `pillow` |
| NLP | LLM | `transformers` | Transformer | Tokenizer | Sampling | `None` |
| Risk | Fraud detection | `sklearn` | Estimator | `None` | `None` | `None` |
| Search | Vector Search | `openai` | OpenAI Embedding | `None` | `None` | `None` |

## PyTorch

PyTorch is the most flexible framework we have integrated. It allows users
to define arbitrary logic in the forward pass, and use backpropagation 
training to calibrate models on the data.

```python
from pinnacledb.ext.torch import TorchModel
m = TorchModel(
    '<model-id>',
    object=MyTorchModule,    # any module programmable in `torch`
    preprocess=my_preproces_function,     # any callable
    postprocess=my_postprocess_function,      # any callable
    encoder=my_encoder                      # any `Encoder` instance
)
```

## Tranformers

Transformers provides a large compendium of pre-trained and pre-defined architectures and pipelines. Their `transformers.Pipeline` abstraction fits well with the `Model` framework:

```python
from pinnacledb.ext.transformers import TransformersModel
m = TransformersModel(
    '<model-id>',
    object=Model,    # a `torch` model compatible with `transformers`
    preprocess=my_preproces_function,     # tokenizer, processor or similar
    postprocess=my_postprocess_function,      # a decoding function
    encoder=my_encoder                      # any `Encoder` instance
)
```

## Sklearn

Sklearn provides a large library of classical estimators and non-deep learning machine learning algorithms. These algorithms mostly work directly with numerical data:

```python
from pinnacledb.ext.sklearn import SklearnModel

m = SklearnModel(
    '<model-id>',
    object=<estimator>,    # `sklearn.base.BaseEstimator` or `sklearn.pipeline.Pipeline`
    preprocess=<preprocess>,    # callable
    postprocess=<postprocess>,    # callable
    encoder=<encoder>,    # `Encoder` instance
)
```

## OpenAI

Since OpenAI consists of calls to an external API, it's model definitions are slightly different:

```python
from pinnacledb.ext.openai import OpenAIEmbedding, OpenAIChatCompletion

m1 = OpenAIEmbedding(model='<model-id-1>')
m2 = OpenAIChatCompletion(model='<model-id-2>')
```

## Quickly porting models to SuperDuperDB

`pinnacle(model)` provides a shortcut to importing the model class directly:

```python
from pinnacledb import pinnacle
from sklearn.svm import SVM
from torch.nn import Linear
from transformers import pipeline

@pinnacle
def my_custom_function(x):
    return (x + 2) ** 2

svm = pinnacle(SVM())
linear = pinnacle(Linear(10, 20))
pipeline = pinnacle(pipeline...)
```

(predictmodel)=
## Applying models to data with `.predict`

All of the models which we created in the previous step are now ready to be applied to the database:

```python
>>> from pinnacledb.db.mongodb.query import Collection
>>> coll = Collection('my_data')
>>> svm.predict(X='x', db=db, select=coll.find())
# Wait a bit
>>> db.execute(coll.find_one())
Document({
    "_id": ObjectId('64b6ba93f8af205501ca7748'),
    'x': Encodable(x=torch.tensor([...])),
    '_outputs': {'x': {'svm': 1}}
})
```

A similar result may be obtained by replaced the `svm` by any of the other models above.

(fitmodel)=
## Training models on data with `.fit`

Using the same analogy to `sklearn` above, SuperDuperDB supports "in-database" training of models:

```python
>>> svm.fit(
    X='x', y='y', db=db, select=coll.find({'_fold': 'train'})
)
# Lots of output corresponding to training here
```
## Model design

Models in SuperDuperDB differ from models in the standard AI frameworks, by
including several additional aspects:

- [preprocessing](preprocessing)
- [postprocessing](postprocessing)
- [output encoding](encoding)

### Preprocessing

All models in SuperDuperDB include the keyword argument `preprocess`. The exact meaning of this varies from framework to framework, however in general:

```{important}
`Model.preprocess` is a function which takes an individual data-point from the database, 
and prepares it for processing by the AI framework model
```

For example:

- In PyTorch (`torch`) computer vision models, a preprocessing function might:
  - Crop the image
  - Normalize the pixel values by precomputed constants
  - Resize the image
  - Convert the image to a tensor
- In Hugging Face `transformers`, and NLP model will:
  - Tokenize a sentence into word-pieces
  - Convert each word piece into a numerical ID
  - Truncate and pad the IDs
  - Compute a mask
- In Scikit-Learn, estimators operate purely at the numerical level
  - Preprocessing may be added exactly as for PyTorch
  - Alternatively users may use a `sklearn.pipeline.Pipeline` explicitly

### Postprocessing

All models in SuperDuperDB include the keyword argument `postprocess`. The goal here 
is to take the numerical estimates of a model, and convert these to a form to 
be used by database users. Examples are:

- Converting a softmax over a dictionary in NLP to point estimates and human-readable strings
- Converting a generated image-tensor into JPG or PNG format
- Performing additional inference logic, such as beam-search in neural translation

### Encoding

The aim of postprocessing is to provide outputs in a operationally useful
form. However, often this form isn't directly amenable to insertion in the `DB`.
Datastores don't typically support images or tensors natively. Consequently 
each model takes the keyword `encoder`, allowing users to specify exactly
how outputs are stored in the database as `bytes`, if not supported natively 
by the database. Read more [here](encoders).

## Supported frameworks

SuperDuperDB has native support for:

- PyTorch
- Hugging-Face
- Sklearn
- OpenAI

Other model frameworks may be used for inference only (`model.predict`).

(daemonize)=
## Daemonizing models with listeners

Models can be configured so that, when new data is inserted through SuperDuperDB database, 
then the models spring into action, processing this new data, and repopulating outputs back 
into the database.

```python
>>> model.predict(X='input_col', db=db, select=coll.find(), listen=True)
```

An equivalent syntax is the following:

```python
>>> from pinnacledb.container.listener import Listener
>>> db.add(
...    Listener(
...        model=model,
...        select=coll.find(),
...        key='input_col',
...    )
... )
```

After setting up a `Listener`, whenever data is inserted or updated, jobs are created 
which save the outputs of the model in the `"_outputs"` field.

A `Listener` may also be configured in [cluster mode](clustersection), to listen for changes coming in 
from any sources - i.e. changes are not just detected through the SuperDuperDB system. 
Read more about that [here](CDC).