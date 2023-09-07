# Turn your classical-database into a vector-database with SuperDuperDB

In this notebook we show how you can use SuperDuperDB to turn your classical database into a vector-search database.

In this example, we'll be using the `sentence_transformers` with `pinnacledb` python package.
In addition, we'll be accessing the OpenAI API. In order to get these working you'll need to install the packages:


```python
!pip install sentence-transformers
!pip install pinnacledb
```

And set the `OPEN_AI_KEY` as environment variable


```python
import os
os.environ['OPENAI_API_KEY'] = '<YOUR-OPENAI-KEY>'
```

In order to access SuperDuperDB, we'll wrap our standard database connector with the `pinnacle` decorator.
This will transform the functionality of your database into a **super-duper** database:


```python
from pinnacledb import pinnacle
import pymongo

db = pymongo.MongoClient().documents
db = pinnacle(db)
```

In this notebook we upload some wikipedia documents from a wikipedia dump. You can find this raw data here https://dumps.wikimedia.org/enwiki/.

We've preprocessed the data, extracting titles and abstracts from each document. We can use this as a test bed for search, by simulating a "typed query" using the title, and indexing the document based on the abstracts only.


```python
import json
import random 

with open(f'{os.environ["HOME"]}/data/wikipedia/abstracts.json') as f:
    data = json.load(f)
data = random.sample(data, 1000)
```

Here's a snapshot of the data:


```python
data[:2]
```

We now insert the data into MongoDB using the SuperDuperDB client:


```python
from pinnacledb.db.mongodb.query import Collection

collection = Collection(name='wikipedia')
```


```python
from pinnacledb.container.document import Document

db.execute(collection.insert_many([Document(r) for r in data]))
```

We can verify that the documents are in the database:


```python
r = db.execute(collection.find_one())
r.unpack()
```

Creating a vector-index in SuperDuperDB involves two things:

- Creating a model which is used to compute vectors (in this case `OpenAIEmbedding`)
- Daemonizing this model on a key (`Listener`), so that when new data are added, these are vectorized using the key

Sentence Transformers are supported by SuperDuperDB, with a wrapper that allows the chosen model to 
communicate directly with SuperDuperDB. The `encoder` argument specifies how the outputs of the models
are saved in the `Datalayer`.


```python
import sentence_transformers
from pinnacledb.container.model import Model
from pinnacledb.ext.numpy.array import array

model = Model(
    identifier='all-MiniLM-L6-v2',
    object=sentence_transformers.SentenceTransformer('all-MiniLM-L6-v2'),
    encoder=array('float32', shape=(384,)),
    predict_method='encode',
    batch_predict=True,
)
```

SuperDuperDB also has inbuilt support for OpenAI. You can also integrate APIs from clients, such as the CoherAI
client using the Model wrapper:


```python
from pinnacledb.ext.openai.model import OpenAIEmbedding

model = OpenAIEmbedding(model='text-embedding-ada-002')
```

We can test our model (whichever we've chosen) like this


```python
model.predict('This is a test', one=True)
```

We've verified our model gives us vectorial outputs, now let's add the search functionality using this model:


```python
from pinnacledb.container.vector_index import VectorIndex
from pinnacledb.container.listener import Listener
from pinnacledb.ext.numpy.array import array

db.add(
    VectorIndex(
        identifier=f'wiki-index-{model.identifier}',
        indexing_listener=Listener(
            model=model,
            key='abstract',
            select=collection.find(),
            predict_kwargs={'max_chunk_size': 1000},
        ),
        compatible_listener=Listener(
            model=model,
            key='title',
            select=collection.find(),
            active=False,
        ),
    )
)
```

We can inspect the functionality which was added like this. The above command creates several components in the single call:

- *model*
- *listener*
- *vector_index*


```python
db.show('model')
```


```python
db.show('listener')
```


```python
db.show('vector_index')
```

We can now test a few vector searches. The way to do this in combination with your classical database
(in this case MongoDB) is to pre-pend the standard query, with a similarity comparison via `like`.

The item inside `like` is vectorized and compared with the stored vectors. In order for this to work, the keys in the 
first parameter to `like` must match those configured in the `Listener` instances inside the `VectorIndex`. The results are then filtered
using the classical query part:


```python
cur = db.execute(
    collection
        .like({'title': 'articles about sport'}, n=10, vector_index=f'wiki-index-{model.identifier}')
        .find({}, {'title': 1})
)

for r in cur:
    print(r)
```

The benefit of having this combination is demonstrated in this query:


```python
cur = db.execute(
    collection
        .like({'title': 'articles about sport'}, n=100, vector_index=f'wiki-index-{model.identifier}')
        .find({'title': {'$regex': '.*Australia'}})
)

for r in cur:
    print(r['title'])
```
