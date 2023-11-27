---
sidebar_position: 2
---

# Setting up tables and encodings

`pinnacledb` has flexible support for data-types. In both MongoDB and SQL databases,
one uses `pinnacledb.Encoder` to define one's own data-types.

## Encoders

To do that, one instantiates the `Encoder` class with functions which go to-and-from `bytes`.

Here is an `Encoder` which encodes `numpy.ndarray` instances to `bytes`:

```python
import numpy

my_array = Encoder(
    'my-array',
    encoder=lambda x: memoryview(x).tobytes(),
    decode=lambda x: numpy.frombuffer(x),
)
```

Here's a more interesting `Encoder` which encoders audio from `numpy.array` format to `.wav` file `bytes`:

```python
import librosa
import io
import soundfile


def decoder(x):
    buffer = io.BytesIO(x)
    return librosa.load(buffer)


def encoder(x):
    buffer = io.BytesIO()
    soundfile.write(buffer)
    return buffer.getvalue()


audio = Encoder('audio', encoder=encoder, decoder=decoder)
```

It's completely open to the user how exactly the `encoder` and `decoder` arguments are set.

You may include this `Encoder` in models, data-insers and more. You can also directly 
register `audio` in the system, using:

```python
db.add(audio)
```

## Schemas for SQL

In SQL, one needs to define a schemas to work with tables in `pinnacledb`. The `pinnacledb.Schema` 
builds on top of `Encoder` and allows developers to combine standard data-types used in standard 
use-cases, with bespoke data-types via `Encoder`, as defined by, for instance, `audio` above.

To register/ create a `Table` with a `Schema` in `pinnacledb`, one uses `pinnacledb.backends.ibis.Table`:

```python
from pinnacledb.backends.ibis import Table, dtype
from pinnacledb import Table

db.add(
    Table(
        'my-table',
        schema=Schema(
            'my-schema',
            fields={'txt': dtype('str'), 'audio': audio, 'array': my_array}
        )
    )
)
```

In this invocation, we create a `Table` with 2 columns, one with `str` values and one with `audio` values.
When data is inserted using the `db` connection, it is inserted into those columns, and the `audio` component
is used to convert the data into `bytes`.