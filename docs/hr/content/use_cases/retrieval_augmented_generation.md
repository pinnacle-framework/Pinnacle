---
sidebar_label: Retrieval augmented generation
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<!-- TABS -->
# Retrieval augmented generation

The first step in any SuperDuperDB application is to connect to your data-backend with SuperDuperDB:

<!-- TABS -->
## Configure your production system

:::note
If you would like to use the production features 
of SuperDuperDB, then you should set the relevant 
connections and configurations in a configuration 
file. Otherwise you are welcome to use "development" mode 
to get going with SuperDuperDB quickly.
:::

```python
import os

os.makedirs('.pinnacledb', exist_ok=True)
os.environ['pinnacleDB_CONFIG'] = '.pinnacledb/config.yaml'
```


<Tabs>
    <TabItem value="MongoDB Community" label="MongoDB Community" default>
        ```python
        CFG = '''
        data_backend: mongodb://127.0.0.1:27017/documents
        artifact_store: filesystem://./artifact_store
        cluster:
          cdc:
            strategy: null
            uri: ray://127.0.0.1:20000
          compute:
            uri: ray://127.0.0.1:10001
          vector_search:
            backfill_batch_size: 100
            type: in_memory
            uri: http://127.0.0.1:21000
        '''        
        ```
    </TabItem>
    <TabItem value="MongoDB Atlas" label="MongoDB Atlas" default>
        ```python
        CFG = '''
        artifact_store: filesystem://<path-to-artifact-store>
        cluster: 
            compute: ray://<ray-host>
            cdc:    
                uri: http://<cdc-host>:<cdc-port>
            vector_search:
                uri: http://<vector-search-host>:<vector-search-port>
                type: native
        databackend: mongodb+srv://<user>:<password>@<mongo-host>:27017/documents
        '''        
        ```
    </TabItem>
    <TabItem value="SQLite" label="SQLite" default>
        ```python
        CFG = '''
        artifact_store: filesystem://<path-to-artifact-store>
        cluster: 
            compute: ray://<ray-host>
            cdc:    
                uri: http://<cdc-host>:<cdc-port>
            vector_search:
                uri: http://<vector-search-host>:<vector-search-port>
        databackend: sqlite://<path-to-db>.db
        '''        
        ```
    </TabItem>
    <TabItem value="MySQL" label="MySQL" default>
        ```python
        CFG = '''
        artifact_store: filesystem://<path-to-artifact-store>
        cluster: 
            compute: ray://<ray-host>
            cdc:    
                uri: http://<cdc-host>:<cdc-port>
            vector_search:
                uri: http://<vector-search-host>:<vector-search-port>
        databackend: mysql://<user>:<password>@<host>:<port>/database
        '''        
        ```
    </TabItem>
    <TabItem value="Oracle" label="Oracle" default>
        ```python
        CFG = '''
        artifact_store: filesystem://<path-to-artifact-store>
        cluster: 
            compute: ray://<ray-host>
            cdc:    
                uri: http://<cdc-host>:<cdc-port>
            vector_search:
                uri: http://<vector-search-host>:<vector-search-port>
        databackend: mssql://<user>:<password>@<host>:<port>
        '''        
        ```
    </TabItem>
    <TabItem value="PostgreSQL" label="PostgreSQL" default>
        ```python
        CFG = '''
        artifact_store: filesystem://<path-to-artifact-store>
        cluster: 
            compute: ray://<ray-host>
            cdc:    
                uri: http://<cdc-host>:<cdc-port>
            vector_search:
                uri: http://<vector-search-host>:<vector-search-port>
        databackend: postgres://<user>:<password>@<host>:<port</<database>
        '''        
        ```
    </TabItem>
    <TabItem value="Snowflake" label="Snowflake" default>
        ```python
        CFG = '''
        artifact_store: filesystem://<path-to-artifact-store>
        metadata_store: sqlite://<path-to-sqlite-db>.db
        cluster: 
            compute: ray://<ray-host>
            cdc:    
                uri: http://<cdc-host>:<cdc-port>
            vector_search:
                uri: http://<vector-search-host>:<vector-search-port>
        databackend: snowflake://<user>:<password>@<account>/<database>
        '''        
        ```
    </TabItem>
    <TabItem value="Clickhouse" label="Clickhouse" default>
        ```python
        CFG = '''
        artifact_store: filesystem://<path-to-artifact-store>
        metadata_store: sqlite://<path-to-sqlite-db>.db
        cluster: 
            compute: ray://<ray-host>
            cdc:    
                uri: http://<cdc-host>:<cdc-port>
            vector_search:
                uri: http://<vector-search-host>:<vector-search-port>
        databackend: clickhouse://<user>:<password>@<host>:<port>
        '''        
        ```
    </TabItem>
</Tabs>
```python
with open(os.environ['pinnacleDB_CONFIG'], 'w') as f:
    f.write(CFG)
```

<!-- TABS -->
## Start your cluster

:::note
Starting a SuperDuperDB cluster is useful in production and model development
if you want to enable scalable compute, access to the models by multiple users for collaboration, 
monitoring.

If you don't need this, then it is simpler to start in development mode.
:::


<Tabs>
    <TabItem value="Experimental Cluster" label="Experimental Cluster" default>
        ```python
        !python -m pinnacledb local-cluster up        
        ```
    </TabItem>
    <TabItem value="Docker-Compose" label="Docker-Compose" default>
        ```python
        !make testenv_image
        !make testenv_init        
        ```
    </TabItem>
</Tabs>
```python
from pinnacledb import pinnacle

db = pinnacle()
```

<!-- TABS -->
## Connect to SuperDuperDB

:::note
Note that this is only relevant if you are running SuperDuperDB in development mode.
Otherwise refer to "Configuring your production system".
:::


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
    <TabItem value="MySQL" label="MySQL" default>
        ```python
        from pinnacledb import pinnacle
        
        user = 'pinnacle'
        password = 'pinnacle'
        port = 3306
        host = 'localhost'
        database = 'test_db'
        
        db = pinnacle(f"mysql://{user}:{password}@{host}:{port}/{database}")        
        ```
    </TabItem>
    <TabItem value="Oracle" label="Oracle" default>
        ```python
        from pinnacledb import pinnacle
        
        user = 'sa'
        password = 'pinnacle#1'
        port = 1433
        host = 'localhost'
        
        db = pinnacle(f"mssql://{user}:{password}@{host}:{port}")        
        ```
    </TabItem>
    <TabItem value="PostgreSQL" label="PostgreSQL" default>
        ```python
        !pip install psycopg2
        from pinnacledb import pinnacle
        
        user = 'postgres'
        password = 'postgres'
        port = 5432
        host = 'localhost'
        database = 'test_db'
        db_uri = f"postgres://{user}:{password}@{host}:{port}/{database}"
        
        db = pinnacle(db_uri, metadata_store=db_uri.replace('postgres://', 'postgresql://'))        
        ```
    </TabItem>
    <TabItem value="Snowflake" label="Snowflake" default>
        ```python
        from pinnacledb import pinnacle
        
        user = "pinnacleuser"
        password = "pinnaclepassword"
        account = "XXXX-XXXX"  # ORGANIZATIONID-USERID
        database = "FREE_COMPANY_DATASET/PUBLIC"
        
        snowflake_uri = f"snowflake://{user}:{password}@{account}/{database}"
        
        db = pinnacle(
            snowflake_uri, 
            metadata_store='sqlite:///your_database_name.db',
        )        
        ```
    </TabItem>
    <TabItem value="Clickhouse" label="Clickhouse" default>
        ```python
        from pinnacledb import pinnacle
        
        user = 'default'
        password = ''
        port = 8123
        host = 'localhost'
        
        db = pinnacle(f"clickhouse://{user}:{password}@{host}:{port}", metadata_store=f'mongomock://meta')        
        ```
    </TabItem>
    <TabItem value="DuckDB" label="DuckDB" default>
        ```python
        from pinnacledb import pinnacle
        
        db = pinnacle('duckdb://mydb.duckdb')        
        ```
    </TabItem>
    <TabItem value="Pandas" label="Pandas" default>
        ```python
        from pinnacledb import pinnacle
        
        db = pinnacle(['my.csv'], metadata_store=f'mongomock://meta')        
        ```
    </TabItem>
    <TabItem value="MongoMock" label="MongoMock" default>
        ```python
        from pinnacledb import pinnacle
        
        db = pinnacle('mongomock:///test_db')        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Get useful sample data


<Tabs>
    <TabItem value="Text" label="Text" default>
        ```python
        !curl -O https://pinnacledb-public-demo.s3.amazonaws.com/text.json
        import json
        
        with open('text.json', 'r') as f:
            data = json.load(f)        
        ```
    </TabItem>
    <TabItem value="PDF" label="PDF" default>
        ```python
        !curl -O https://pinnacledb-public-demo.s3.amazonaws.com/pdfs.zip && unzip -o pdfs.zip
        import os
        
        data = [f'pdfs/{x}' for x in os.listdir('./pdfs')]
        data        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Setup tables or collections


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        # Note this is an optional step for MongoDB
        # Users can also work directly with `DataType` if they want to add
        # custom data
        from pinnacledb import Schema, DataType
        from pinnacledb.backends.mongodb import Collection
        
        table_or_collection = Collection('documents')
        USE_SCHEMA = False
        datatype = None
        
        if USE_SCHEMA and isinstance(datatype, DataType):
            schema = Schema(fields={'x': datatype})
            db.apply(schema)        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        from pinnacledb.backends.ibis import Table
        from pinnacledb import Schema, DataType
        from pinnacledb.backends.ibis.field_types import dtype
        
        datatype = "str"
        
        if isinstance(datatype, DataType):
            schema = Schema(identifier="schema", fields={"id": dtype("str"), "x": datatype})
        else:
            schema = Schema(
                identifier="schema", fields={"id": dtype("str"), "x": dtype(datatype)}
            )
        
        table_or_collection = Table('documents', schema=schema)
        
        db.apply(table_or_collection)        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Insert data

In order to create data, we need to create a `Schema` for encoding our special `Datatype` column(s) in the databackend.


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        from pinnacledb import Document
        
        def do_insert(data):
            schema = None
            
            if schema is None and datatype is None:
                data = [Document({'x': x}) for x in data]
                db.execute(table_or_collection.insert_many(data))
            elif schema is None and datatype is not None:
                data = [Document({'x': datatype(x)}) for x in data]
                db.execute(table_or_collection.insert_many(data))
            else:
                data = [Document({'x': x}) for x in data]
                db.execute(table_or_collection.insert_many(data, schema='my_schema'))        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        from pinnacledb import Document
        
        def do_insert(data):
            db.execute(table_or_collection.insert([Document({'id': str(idx), 'x': x}) for idx, x in enumerate(data)]))        
        ```
    </TabItem>
</Tabs>
```python
do_insert(data[:-len(data) // 4])
```

<!-- TABS -->
## Build simple select queries


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        
        select = table_or_collection.find({})        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        
        select = table_or_collection.to_query()        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Create Model Output Type


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        model_output_dtype = None        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        from pinnacledb.backends.ibis.field_types import dtype
        model_output_dtype = dtype('str')        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Apply a chunker for search

:::note
Note that applying a chunker is ***not*** mandatory for search.
If your data is already chunked (e.g. short text snippets or audio) or if you
are searching through something like images, which can't be chunked, then this
won't be necessary.
:::


<Tabs>
    <TabItem value="Text" label="Text" default>
        ```python
        from pinnacledb import objectmodel
        
        CHUNK_SIZE = 200
        
        @objectmodel(flatten=True, model_update_kwargs={'document_embedded': False}, datatype=model_output_dtype)
        def chunker(text):
            text = text.split()
            chunks = [' '.join(text[i:i + CHUNK_SIZE]) for i in range(0, len(text), CHUNK_SIZE)]
            return chunks        
        ```
    </TabItem>
    <TabItem value="PDF" label="PDF" default>
        ```python
        !pip install -q "unstructured[pdf]"
        from pinnacledb import objectmodel
        from unstructured.partition.pdf import partition_pdf
        
        CHUNK_SIZE = 500
        
        @objectmodel(flatten=True, model_update_kwargs={'document_embedded': False}, datatype=model_output_dtype)
        def chunker(pdf_file):
            elements = partition_pdf(pdf_file)
            text = '\n'.join([e.text for e in elements])
            chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
            return chunks        
        ```
    </TabItem>
</Tabs>
Now we apply this chunker to the data by wrapping the chunker in `Listener`:

```python
from pinnacledb import Listener

upstream_listener = Listener(
    model=chunker,
    select=select,
    key='x',
)

db.apply(upstream_listener)
```

## Select outputs of upstream listener

:::note
This is useful if you have performed a first step, such as pre-computing 
features, or chunking your data. You can use this query to 
operate on those outputs.
:::


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        from pinnacledb.backends.mongodb import Collection
        
        indexing_key = upstream_listener.outputs_key
        select = Collection(upstream_listener.outputs).find()        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        indexing_key = upstream_listener.outputs_key
        select = db.load("table", upstream_listener.outputs).to_query()        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Build text embedding model


<Tabs>
    <TabItem value="OpenAI" label="OpenAI" default>
        ```python
        !pip install openai
        from pinnacledb.ext.openai import OpenAIEmbedding
        model = OpenAIEmbedding(identifier='text-embedding-ada-002')        
        ```
    </TabItem>
    <TabItem value="JinaAI" label="JinaAI" default>
        ```python
        from pinnacledb.ext.jina import JinaEmbedding
         
        # define the model
        model = JinaEmbedding(identifier='jina-embeddings-v2-base-en')        
        ```
    </TabItem>
    <TabItem value="Sentence-Transformers" label="Sentence-Transformers" default>
        ```python
        !pip install sentence-transformers
        from pinnacledb import vector
        import sentence_transformers
        from pinnacledb.ext.sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer(
            identifier="embedding",
            object=sentence_transformers.SentenceTransformer("BAAI/bge-small-en"),
            datatype=vector(shape=(1024,)),
            postprocess=lambda x: x.tolist(),
            predict_kwargs={"show_progress_bar": True},
        )        
        ```
    </TabItem>
    <TabItem value="Transformers" label="Transformers" default>
        ```python
        import dataclasses as dc
        from pinnacledb import vector
        from pinnacledb.components.model import Model, ensure_initialized, Signature
        from transformers import AutoTokenizer, AutoModel
        import torch
        
        @dc.dataclass(kw_only=True)
        class TransformerEmbedding(Model):
            signature: Signature = 'singleton'
            pretrained_model_name_or_path : str
        
            def init(self):
                self.tokenizer = AutoTokenizer.from_pretrained(self.pretrained_model_name_or_path)
                self.model = AutoModel.from_pretrained(self.pretrained_model_name_or_path)
                self.model.eval()
        
            @ensure_initialized
            def predict_one(self, x):
                return self.predict([x])[0]
                
            @ensure_initialized
            def predict(self, dataset):
                encoded_input = self.tokenizer(dataset, padding=True, truncation=True, return_tensors='pt')
                # Compute token embeddings
                with torch.no_grad():
                    model_output = self.model(**encoded_input)
                    # Perform pooling. In this case, cls pooling.
                    sentence_embeddings = model_output[0][:, 0]
                # normalize embeddings
                sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
                return sentence_embeddings.tolist()
        
        
        model = TransformerEmbedding(identifier="embedding", pretrained_model_name_or_path="BAAI/bge-small-en", datatype=vector(shape=(384, )))        
        ```
    </TabItem>
</Tabs>
```python
print(len(model.predict_one("What is SuperDuperDB")))
```

## Create vector-index

```python
vector_index_name = 'my-vector-index'
```


<Tabs>
    <TabItem value="1-Modality" label="1-Modality" default>
        ```python
        from pinnacledb import VectorIndex, Listener
        
        jobs, _ = db.add(
            VectorIndex(
                vector_index_name,
                indexing_listener=Listener(
                    key=indexing_key,      # the `Document` key `model` should ingest to create embedding
                    select=select,       # a `Select` query telling which data to search over
                    model=model,         # a `_Predictor` how to convert data to embeddings
                )
            )
        )        
        ```
    </TabItem>
    <TabItem value="2-Modalities" label="2-Modalities" default>
        ```python
        from pinnacledb import VectorIndex, Listener
        
        jobs, _ = db.add(
            VectorIndex(
                vector_index_name,
                indexing_listener=Listener(
                    key=indexing_key,      # the `Document` key `model` should ingest to create embedding
                    select=select,       # a `Select` query telling which data to search over
                    model=model,         # a `_Predictor` how to convert data to embeddings
                ),
                compatible_listener=Listener(
                    key=compatible_key,      # the `Document` key `model` should ingest to create embedding
                    model=compatible_model,         # a `_Predictor` how to convert data to embeddings
                    active=False,
                    select=None,
                )
            )
        )        
        ```
    </TabItem>
</Tabs>
```python
query_table_or_collection = select.table_or_collection
```

```python
sample_datapoint = data[0]
query = "Tell me about the SuperDuperDb"
```

<!-- TABS -->
## Perform a vector search

```python
from pinnacledb import Document

item = Document({indexing_key: sample_datapoint})
```

Once we have this search target, we can execute a search as follows:


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        select = query_table_or_collection.like(item, vector_index=vector_index_name, n=10).find()        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        select = query_table_or_collection.like(item)        
        ```
    </TabItem>
</Tabs>
```python
results = db.execute(select)
```

<!-- TABS -->
## Create Vector Search Model

```python
from pinnacledb.base.serializable import Variable
item = {indexing_key: Variable('query')}
```

```python
from pinnacledb.components.model import QueryModel

vector_search_model = QueryModel(
    identifier="VectorSearch",
    select=select,
    postprocess=lambda docs: [{"text": doc[indexing_key], "_source": doc["_source"]} for doc in docs]
)
vector_search_model.db = db
```

```python
vector_search_model.predict_one(query=query)
```

<!-- TABS -->
## Build LLM


<Tabs>
    <TabItem value="OpenAI" label="OpenAI" default>
        ```python
        !pip install openai
        from pinnacledb.ext.openai import OpenAIChatCompletion
        
        llm = OpenAIChatCompletion(identifier='llm', model='gpt-3.5-turbo')        
        ```
    </TabItem>
    <TabItem value="Anthropic" label="Anthropic" default>
        ```python
        
        from pinnacledb.ext.anthropic import AnthropicCompletions
        llm = AnthropicCompletions(identifier='llm', model='claude-2')        
        ```
    </TabItem>
    <TabItem value="vLLM" label="vLLM" default>
        ```python
        !pip install vllm
        from pinnacledb.ext.vllm import VllmModel
        
        predict_kwargs = {
            "max_tokens": 1024,
            "temperature": 0.8,
        }
        
        
        llm = VllmModel(
            identifier="llm",
            model_name="TheBloke/Mistral-7B-Instruct-v0.2-AWQ",
            vllm_kwargs={
                "gpu_memory_utilization": 0.7,
                "max_model_len": 1024,
                "quantization": "awq",
            },
            predict_kwargs=predict_kwargs,
        )        
        ```
    </TabItem>
    <TabItem value="Transformers" label="Transformers" default>
        ```python
        !pip install transformers datasets bitsandbytes accelerate
        from pinnacledb.ext.transformers import LLM
        
        llm = LLM.from_pretrained("mistralai/Mistral-7B-Instruct-v0.2", load_in_8bit=True, device_map="cuda", identifier="llm", predict_kwargs=dict(max_new_tokens=128))        
        ```
    </TabItem>
    <TabItem value="Llama.cpp" label="Llama.cpp" default>
        ```python
        !pip install llama_cpp_python
        # !huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF mistral-7b-instruct-v0.2.Q4_K_M.gguf --local-dir . --local-dir-use-symlinks False
        
        from pinnacledb.ext.llamacpp.model import LlamaCpp
        llm = LlamaCpp(identifier="llm", model_name_or_path="mistral-7b-instruct-v0.2.Q4_K_M.gguf")        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Answer question with LLM


<Tabs>
    <TabItem value="No-context" label="No-context" default>
        ```python
        
        llm.predict_one(query)        
        ```
    </TabItem>
    <TabItem value="Prompt" label="Prompt" default>
        ```python
        from pinnacledb import objectmodel
        from pinnacledb.components.graph import Graph, input_node
        
        @objectmodel
        def build_prompt(query):
            return f"Translate the sentence into German: {query}"
        
        in_ = input_node('query')
        prompt = build_prompt(query=in_)
        answer = llm(X=prompt)
        prompt_llm = answer.to_graph("prompt_llm")
        prompt_llm.predict_one(query)[0]        
        ```
    </TabItem>
    <TabItem value="Context" label="Context" default>
        ```python
        from pinnacledb import objectmodel
        from pinnacledb.components.graph import Graph, input_node
        
        prompt_template = (
            "Use the following context snippets, these snippets are not ordered!, Answer the question based on this context.\n"
            "{context}\n\n"
            "Here's the question: {query}"
        )
        
        
        @objectmodel
        def build_prompt(query, docs):
            chunks = [doc["text"] for doc in docs]
            context = "\n\n".join(chunks)
            prompt = prompt_template.format(context=context, query=query)
            return prompt
            
        
        in_ = input_node('query')
        vector_search_results = vector_search_model(query=in_)
        prompt = build_prompt(query=in_, docs=vector_search_results)
        answer = llm(X=prompt)
        context_llm = answer.to_graph("context_llm")
        context_llm.predict_one(query)        
        ```
    </TabItem>
</Tabs>
