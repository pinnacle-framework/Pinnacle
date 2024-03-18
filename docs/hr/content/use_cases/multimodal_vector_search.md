---
sidebar_label: Multimodal vector search
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<!-- TABS -->
# Multimodal vector search

The first step in any SuperDuperDB application is to connect to your data-backend with SuperDuperDB:

<!-- TABS -->
## Connect to SuperDuperDB


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        from pinnacledb import pinnacle
        
        db = pinnacle('mongodb://localhost:27017/documents')        
        ```
    </TabItem>
    <TabItem value="SQLite" label="SQLite" default>
        ```python
        from pinnacledb import pinnacle
        
        db = pinnacle('sqlite://my_db.db')        
        ```
    </TabItem>
</Tabs>
Once you have done that you are ready to define your datatype(s) which you would like to "search".

<!-- TABS -->
## Create datatype


<Tabs>
    <TabItem value="Audio" label="Audio" default>
        ```python
        ...        
        ```
    </TabItem>
    <TabItem value="Video" label="Video" default>
        ```python
        ...        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Insert data

In order to create data, we need create a `Schema` for encoding our special `Datatype` column(s) in the databackend.

Here's some sample data to work with:


<Tabs>
    <TabItem value="Text" label="Text" default>
        ```python
        !curl -O https://jupyter-sessions.s3.us-east-2.amazonaws.com/text.json
        
        import json
        with open('text.json') as f:
            data = json.load(f)        
        ```
    </TabItem>
    <TabItem value="Images" label="Images" default>
        ```python
        !curl -O https://jupyter-sessions.s3.us-east-2.amazonaws.com/images.zip
        !unzip images.zip
        
        import os
        data = [{'image': f'file://image/{file}'} for file in os.listdir('./images')]        
        ```
    </TabItem>
    <TabItem value="Audio" label="Audio" default>
        ```python
        !curl -O https://jupyter-sessions.s3.us-east-2.amazonaws.com/audio.zip
        !unzip audio.zip
        
        import os
        data = [{'audio': f'file://audio/{file}'} for file in os.listdir('./audio')]        
        ```
    </TabItem>
</Tabs>
The next code-block is only necessary if you're working with a custom `DataType`:

```python
from pinnacledb import Schema, Document

schema = Schema(
    'my_schema',
    fields={
        'my_key': dt
    }
)

data = [
    Document({'my_key': item}) for item in data
]
```


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        from pinnacledb.backends.mongodb import Collection
        
        collection = Collection('documents')
        
        db.execute(collection.insert_many(data))        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        from pinnacledb.backends.ibis import Table
        
        table = Table(
            'my_table',
            schema=schema,
        )
        
        db.add(table)
        db.execute(table.insert(data))        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Build multimodal embedding models


<Tabs>
    <TabItem value="Text" label="Text" default>
        ```python
        
        ...        
        ```
    </TabItem>
    <TabItem value="Image" label="Image" default>
        ```python
        
        ...        
        ```
    </TabItem>
    <TabItem value="Text-2-Image" label="Text-2-Image" default>
        ```python
        
        ...        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Perform a vector search

- `item` is the item which is to be encoded
- `dt` is the `DataType` instance to apply

```python
from pinnacledb import Document

item = Document({'my_key': dt(item)})
```

Once we have this search target, we can execute a search as follows:


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        from pinnacledb.backends.mongodb import Collection
        
        collection = Collection('documents')
        
        select = collection.find().like(item)        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        
        # Table was created earlier, before preparing vector-search
        table = db.load('table', 'documents')
        
        select = table.like(item)        
        ```
    </TabItem>
</Tabs>
```python
results = db.execute(select)
```

