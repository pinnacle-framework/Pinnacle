# Encoders

## User defined types for serializing arbitrary data

A **encoder** is a Python object registered with a SuperDuperDB collection which manages how
model outputs or database content are converted to and from ``bytes`` so that these may be
stored and retrieved from the database. Creating types is a prerequisite to adding models
which have non-Jsonable outputs to a collection, as well as adding data types to the database
of a more sophisticated variety, such as images, tensors and so forth.

Here are two examples of types, which can be very handy
for many AI models:

```python

class FloatTensor:
    types = (torch.FloatTensor, torch.Tensor)

    @staticmethod
    def encode(x):
        x = x.numpy()
        assert x.dtype == numpy.float32
        return memoryview(x).tobytes()

    @staticmethod
    def decode(bytes_):
        array = numpy.frombuffer(bytes_, dtype=numpy.float32)
        return torch.from_numpy(array).type(torch.float)


class PILImage:
    types = (PIL.Image.Image,)

    @staticmethod
    def encode(x):
        buffer = io.BytesIO()
        x.save(buffer, format='png')
        return buffer.getvalue()

    @staticmethod
    def decode(bytes_):
        return PIL.Image.open(io.BytesIO(bytes_))

```

Each **type** must include an ``.encode`` and a ``.decode`` method. Optionally, the type
will include a tuple of the python classes which belong to that type in the ``.types``
attribute.

A **type** class must be pickleable using python ``pickle`` - SuperDuperDB
stores the pickled object in the database.

Equipped with this class, we can now register a type with the collection:

```python
>>> docs = SuperDuperClient(**opts).my_database.documents
>>> docs.create_type('float_tensor', FloatTensor())
>>> docs.create_type('image', PILImage())
>>> docs.list_types()
['float_tensor', 'image']
# retrieve the type object from the database
>>> docs.types['float_tensor']
    <my_package.FloatTensor at 0x10bbf9270>
```

Let's test the ``"image"`` type by adding a ``PIL.Image`` object to SuperDuperDB:

```python
>>> import requests, PIL.Image, io
>>> bytes_ = requests.get('https://www.pinnacledb.com/logos/white.png').content
>>> image = PIL.Image.open(io.BytesIO(bytes_))
>>> docs.insert_one({'img': image, 'i': 0})
>>> docs.find_one({'i': 0})
{'_id': ObjectId('63fca4325d2a192e05fe154a'),
    'img': <PIL.PngImagePlugin.PngImageFile image mode=RGBA size=531x106>,
    '_fold': 'train'}
```

A more efficient approach which gives the same result, is to add the **type** of the data explicitly like this:

```
>>> docs.insert_one({'img': {'_content': {'bytes': bytes_, 'type': 'image'}}, 'i': 0})
```
