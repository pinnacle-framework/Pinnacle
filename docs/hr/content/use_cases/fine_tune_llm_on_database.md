---
sidebar_label: Fine tune LLM on database
filename: fine_tune_llm_on_database.md
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import DownloadButton from '../DownloadButton';


<!-- TABS -->
# Fine tune LLM on database

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
## Install related dependencies

```python
!pip install transformers torch accelerate trl peft datasets
```

<!-- TABS -->
## Get LLM Finetuning Data

The following are examples of training data in different formats.


<Tabs>
    <TabItem value="Text" label="Text" default>
        ```python
        from datasets import load_dataset
        from pinnacledb.base.document import Document
        dataset_name = "timdettmers/openassistant-guanaco"
        dataset = load_dataset(dataset_name)
        
        train_dataset = dataset["train"]
        eval_dataset = dataset["test"]
        
        train_documents = [
            Document({**example, "_fold": "train"})
            for example in train_dataset
        ][:500]
        eval_documents = [
            Document({**example, "_fold": "valid"})
            for example in eval_dataset
        ][:10]
        
        datas = train_documents + eval_documents        
        ```
    </TabItem>
    <TabItem value="Prompt-Response" label="Prompt-Response" default>
        ```python
        from datasets import load_dataset
        from pinnacledb.base.document import Document
        dataset_name = "mosaicml/instruct-v3"
        dataset = load_dataset(dataset_name)
        
        train_dataset = dataset["train"]
        eval_dataset = dataset["test"]
        
        train_documents = [
            Document({**example, "_fold": "train"})
            for example in train_dataset
        ]
        eval_documents = [
            Document({**example, "_fold": "valid"})
            for example in eval_dataset
        ]
        
        datas = train_documents + eval_documents        
        ```
    </TabItem>
    <TabItem value="Chat" label="Chat" default>
        ```python
        from datasets import load_dataset
        from pinnacledb.base.document import Document
        dataset_name = "philschmid/dolly-15k-oai-style"
        dataset = load_dataset(dataset_name)['train'].train_test_split(0.9)
        
        train_dataset = dataset["train"]
        eval_dataset = dataset["test"]
        
        train_documents = [
            Document({**example, "_fold": "train"})
            for example in train_dataset
        ]
        eval_documents = [
            Document({**example, "_fold": "valid"})
            for example in eval_dataset
        ]
        
        datas = train_documents + eval_documents        
        ```
    </TabItem>
</Tabs>
We can define different training parameters to handle this type of data.


<Tabs>
    <TabItem value="Text" label="Text" default>
        ```python
        # Function for transformation after extracting data from the database
        transform = None
        key = ('text')
        training_kwargs=dict(dataset_text_field="text")        
        ```
    </TabItem>
    <TabItem value="Prompt-Response" label="Prompt-Response" default>
        ```python
        # Function for transformation after extracting data from the database
        def transform(prompt, response):
            return {'text': prompt + response + "</s>"}
        
        key = ('prompt', 'response')
        training_kwargs=dict(dataset_text_field="text")        
        ```
    </TabItem>
    <TabItem value="Chat" label="Chat" default>
        ```python
        # Function for transformation after extracting data from the database
        transform = None
        
        key = ('messages')
        training_kwargs=None        
        ```
    </TabItem>
</Tabs>
Example input_text and output_text


<Tabs>
    <TabItem value="Text" label="Text" default>
        ```python
        data = datas[0]
        input_data, output_text = data["text"].rsplit("### Assistant: ", maxsplit=1)
        input_text += "### Assistant: "
        output_text = output_text.rsplit("### Human:")[0]
        print("Input: --------------")
        print(input_text)
        print("Response: --------------")
        print(output_text)        
        ```
    </TabItem>
    <TabItem value="Prompt-Response" label="Prompt-Response" default>
        ```python
        data = datas[0]
        input_text = data["prompt"]
        output_text = data["response"]
        print("Input: --------------")
        print(input_text)
        print("Response: --------------")
        print(output_text)        
        ```
    </TabItem>
    <TabItem value="Chat" label="Chat" default>
        ```python
        data = datas[0]
        messages = data["messages"]
        input_text = messages[:-1]
        output_text = messages[-1]["content"]
        print("Input: --------------")
        print(input_text)
        print("Response: --------------")
        print(output_text)        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Setup simple tables or collections


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        # If our data is in a format natively supported by MongoDB, we don't need to do anything.
        from pinnacledb.backends.mongodb import Collection
        
        table_or_collection = Collection('documents')
        select = table_or_collection.find({})        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        from pinnacledb.backends.ibis import Table
        from pinnacledb import Schema, DataType
        from pinnacledb.backends.ibis.field_types import dtype
        
        for index, data in enumerate(datas):
            data["id"] = str(index) 
        
        fields = {}
        
        for key, value in data.items():
            fields[key] = dtype(type(value))
        
        schema = Schema(identifier="schema", fields=fields)
        
        table_or_collection = Table('documents', schema=schema)
        
        db.apply(table_or_collection)
        
        select = table_or_collection.select("id", "prompt", "response")        
        ```
    </TabItem>
</Tabs>
<!-- TABS -->
## Insert simple data

In order to create data, we need to create a `Schema` for encoding our special `Datatype` column(s) in the databackend.


<Tabs>
    <TabItem value="MongoDB" label="MongoDB" default>
        ```python
        from pinnacledb import Document
        
        ids, _ = db.execute(table_or_collection.insert_many(datas))        
        ```
    </TabItem>
    <TabItem value="SQL" label="SQL" default>
        ```python
        ids, _ = db.execute(table_or_collection.insert(datas))        
        ```
    </TabItem>
</Tabs>
```python
model_name = "facebook/opt-125m"
```

<!-- TABS -->
## Build A Trainable LLM

### Create an LLM Trainer for training
The parameters of this LLM Trainer are basically the same as `transformers.TrainingArguments`, but some additional parameters have been added for easier training setup.

```python
from pinnacledb.ext.transformers import LLM, LLMTrainer
trainer = LLMTrainer(
    identifier="llm-finetune-trainer",
    output_dir="output/finetune",
    overwrite_output_dir=True,
    max_steps=50,
    # num_train_epochs=3,
    save_total_limit=3,
    logging_steps=10,
    evaluation_strategy="steps",
    save_steps=10,
    eval_steps=10,
    per_device_train_batch_size=1,
    per_device_eval_batch_size=1,
    gradient_accumulation_steps=2,
    max_seq_length=512,
    key=key,
    select=select,
    transform=transform,
    training_kwargs=training_kwargs,
)
```


<Tabs>
    <TabItem value="Lora" label="Lora" default>
        ```python
        trainer.use_lora = True        
        ```
    </TabItem>
    <TabItem value="QLora" label="QLora" default>
        ```python
        trainer.use_lora = True
        trainer.bits = 4        
        ```
    </TabItem>
    <TabItem value="Ray" label="Ray" default>
        ```python
        trainer.use_lora = True
        trainer.bits = 4
        trainer.ray_address = "ray://localhost:10001"        
        ```
    </TabItem>
    <TabItem value="Deepspeed" label="Deepspeed" default>
        ```python
        !pip install deepspeed
        deepspeed = {
            "train_batch_size": "auto",
            "train_micro_batch_size_per_gpu": "auto",
            "gradient_accumulation_steps": "auto",
            "zero_optimization": {
                "stage": 2,
            },
        }
        trainer.use_lora = True
        trainer.bits = 4
        trainer.deepspeed = deepspeed        
        ```
    </TabItem>
    <TabItem value="Multi-GPUS" label="Multi-GPUS" default>
        ```python
        trainer.use_lora = True
        trainer.bits = 4
        trainer.num_gpus = 2        
        ```
    </TabItem>
</Tabs>
Create a trainable LLM model and add it to the database, then the training task will run automatically.

```python
llm = LLM(
    identifier="llm",
    model_name_or_path=model_name,
    trainer=trainer,
    model_kwargs=model_kwargs,
    tokenizer_kwargs=tokenizer_kwargs,
)

db.apply(llm)
```

## Load the trained model
There are two methods to load a trained model:

- **Load the model directly**: This will load the model with the best metrics (if the transformers' best model save strategy is set) or the last version of the model.
- **Use a specified checkpoint**: This method downloads the specified checkpoint, then initializes the base model, and finally pinnacles the checkpoint with the base model. This approach supports custom operations such as resetting flash_attentions, model quantization, etc., during initialization.


<Tabs>
    <TabItem value="Load Trained Model Directly" label="Load Trained Model Directly" default>
        ```python
        llm = db.load("model", "llm")        
        ```
    </TabItem>
    <TabItem value="Use a specified checkpoint" label="Use a specified checkpoint" default>
        ```python
        from pinnacledb.ext.transformers import LLM, LLMTrainer
        experiment_id = db.show("checkpoint")[-1]
        version = None # None means the last checkpoint
        checkpoint = db.load("checkpoint", experiment_id, version=None)
        llm = LLM(
            identifier="llm",
            model_name_or_path=model_name,
            adapter_id=checkpoint,
            model_kwargs=dict(load_in_4bit=True)
        )        
        ```
    </TabItem>
</Tabs>
```python
llm.predict_one(input_text, max_new_tokens=200)
```

<DownloadButton filename="fine_tune_llm_on_database.md" />
