---
sidebar_label: Create datatype
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<!-- TABS -->
# Create datatype

Data types such as "text" or "integer" which are natively support by your `db.databackend` don't need a datatype.

```python
datatype = None
```

Otherwise do one of the following:


<Tabs>
    <TabItem value="Vector" label="Vector" default>
        ```python
        from pinnacledb import vector
        
        datatype = vector(shape=(3, ))        
        ```
    </TabItem>
    <TabItem value="Tensor" label="Tensor" default>
        ```python
        from pinnacledb.ext.torch import tensor
        import torch
        
        datatype = tensor(torch.float, shape=(32, 32, 3))        
        ```
    </TabItem>
    <TabItem value="Array" label="Array" default>
        ```python
        from pinnacledb.ext.numpy import array
        import numpy as np
        
        datatype = array(dtype="float64", shape=(32, 32, 3))        
        ```
    </TabItem>
    <TabItem value="PDF" label="PDF" default>
        ```python
        !pip install PyPDF2
        from pinnacledb import DataType
        from pinnacledb.components.datatype import File
        
        datatype = DataType('pdf', encodable='file')        
        ```
    </TabItem>
    <TabItem value="Text" label="Text" default>
        ```python
        datatype = 'str'        
        ```
    </TabItem>
    <TabItem value="Image" label="Image" default>
        ```python
        from pinnacledb.ext.pillow import pil_image
        import PIL.Image
        
        datatype = pil_image        
        ```
    </TabItem>
    <TabItem value="URI" label="URI" default>
        ```python
        
        datatype = None        
        ```
    </TabItem>
    <TabItem value="Audio" label="Audio" default>
        ```python
        from pinnacledb.ext.numpy import array
        from pinnacledb import DataType
        import scipy.io.wavfile
        import io
        
        
        def encoder(data):
            buffer = io.BytesIO()
            fs = data[0]
            content = data[1]
            scipy.io.wavfile.write(buffer, fs, content)
            return buffer.getvalue()
        
        
        def decoder(data):
            buffer = io.BytesIO(data)
            content = scipy.io.wavfile.read(buffer)
            return content
        
        
        datatype = DataType(
            'wav',
            encoder=encoder,
            decoder=decoder,
            encodable='artifact',
        )        
        ```
    </TabItem>
    <TabItem value="Video" label="Video" default>
        ```python
        from pinnacledb import DataType
        
        # Create an instance of the Encoder with the identifier 'video_on_file' and load_hybrid set to False
        datatype = DataType(
            identifier='video_on_file',
            encodable='artifact',
        )        
        ```
    </TabItem>
    <TabItem value="Encodable" label="Encodable" default>
        ```python
        from pinnacledb import DataType
        import pandas as pd
        
        def encoder(x, info=None):
            return x.to_json()
        
        def decoder(x, info):
            return pd.read_json(x)
            
        datatype = DataType(
            identifier="pandas",
            encoder=encoder,
            decoder=decoder
        )        
        ```
    </TabItem>
    <TabItem value="Artifact" label="Artifact" default>
        ```python
        from pinnacledb import DataType
        import numpy as np
        import pickle
        
        
        def pickle_encode(object, info=None):
            return pickle.dumps(object)
        
        def pickle_decode(b, info=None):
            return pickle.loads(b)
        
        
        datatype = DataType(
            identifier="VectorSearchMatrix",
            encoder=pickle_encode,
            decoder=pickle_decode,
            encodable='artifact',
        )        
        ```
    </TabItem>
</Tabs>
```python
from pinnacledb import DataType
if datatype and isinstance(datatype, DataType):
    db.apply(datatype)
```

