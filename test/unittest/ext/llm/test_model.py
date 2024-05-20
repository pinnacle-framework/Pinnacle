import os
import random
from test.db_config import DBConfig
from test.unittest.ext.llm.utils import check_llm_as_listener_model, check_predict

import pytest

from pinnacledb.backends.ibis.field_types import FieldType
from pinnacledb.backends.mongodb.query import MongoQuery
from pinnacledb.base.document import Document
from pinnacledb.components.dataset import Dataset
from pinnacledb.components.metric import Metric
from pinnacledb.ext.transformers.model import LLM
from pinnacledb.ext.transformers.training import LLMTrainer

TEST_MODEL_NAME = "facebook/opt-125m"
try:
    import datasets
    import peft
    import trl
except ImportError:
    datasets = None
    peft = None
    trl = None

RUN_LLM_FINETUNE = os.environ.get("RUN_LLM_FINETUNE", "0") == "1"


@pytest.mark.parametrize(
    "db", [DBConfig.mongodb_empty, DBConfig.sqldb_empty], indirect=True
)
def test_predict(db):
    """Test chat."""
    model = LLM(identifier="llm", model_name_or_path=TEST_MODEL_NAME)

    check_predict(db, model)


@pytest.mark.parametrize(
    "db", [DBConfig.mongodb_empty, DBConfig.sqldb_empty], indirect=True
)
def test_model_as_listener_model(db):
    model = LLM(
        identifier="llm",
        model_name_or_path=TEST_MODEL_NAME,
        datatype=FieldType('str'),
    )
    check_llm_as_listener_model(db, model)


@pytest.mark.skipif(not RUN_LLM_FINETUNE, reason="RUN_LLM_FINETUNE is not set")
@pytest.mark.skipif(
    not all([datasets, peft, trl]),
    reason="The peft, datasets and trl are not installed",
)
@pytest.mark.parametrize("db", [DBConfig.mongodb_empty], indirect=True)
def test_training(db, tmpdir):
    datas = []
    for i in range(32 + 8):
        text = f"{i}+1={i+1}"
        fold = "train" if i < 32 else "valid"
        datas.append({"text": text, "id": str(i), "fold": fold})

    collection = MongoQuery("doc")
    db.execute(collection.insert_many(list(map(Document, datas))))
    select = collection.find()

    model = LLM(
        identifier="llm",
        model_name_or_path="facebook/opt-125m",
        tokenizer_kwargs=dict(model_max_length=64),
    )
    training_configuration = LLMTrainer(
        identifier="llm-finetune",
        output_dir=str(tmpdir),
        lora_r=64,
        lora_alpha=16,
        lora_dropout=0.05,
        num_train_epochs=3,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        evaluation_strategy="steps",
        eval_steps=1,
        save_strategy="steps",
        save_steps=1,
        save_total_limit=3,
        learning_rate=2e-5,
        weight_decay=0.0,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_strategy="steps",
        logging_steps=1,
        gradient_checkpointing=True,
        report_to=[],
        max_seq_length=64,
    )

    def metric(predictions, targets):
        return random.random()

    model.fit_in_db(
        X="text",
        db=db,
        select=select,
        configuration=training_configuration,
        prefetch_size=1000,
        validation_sets=[
            Dataset(
                identifier="dataset_1",
                select=collection.find({"_fold": "valid"}),
            ),
            Dataset(
                identifier="dataset_2",
                select=collection.find({"_fold": "valid"}),
            ),
        ],
        metrics=[
            Metric(
                identifier="metrics1",
                object=metric,
            ),
            Metric(
                identifier="metrics2",
                object=metric,
            ),
        ],
    )

    checkpoints = os.listdir(tmpdir)
    checkpoints = [
        checkpoint for checkpoint in checkpoints if checkpoint.startswith("checkpoint")
    ]
    checkpoints = sorted(checkpoints, key=lambda x: int(x.split("-")[-1]))

    # Test checkpoints
    assert len(checkpoints) == 3

    # Test multi-lora adapters
    llm_base = LLM(
        identifier="base",
        model_name_or_path="facebook/opt-125m",
        tokenizer_kwargs=dict(model_max_length=64),
    )
    db.add(llm_base)
    for checkpoint in checkpoints:
        llm_checkpoint = LLM(
            identifier=checkpoint,
            adapter_id=os.path.join(tmpdir, checkpoint),
            model_name_or_path="facebook/opt-125m",
            tokenizer_kwargs=dict(model_max_length=64),
        )
        db.add(llm_checkpoint)

    db.add(llm_base)
    db.predict(llm_base.identifier, "1+1=")
    for checkpoint in checkpoints:
        db.predict(checkpoint, "1+1=")
