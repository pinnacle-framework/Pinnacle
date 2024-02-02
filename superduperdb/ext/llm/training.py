import dataclasses as dc
import os
import typing as t
from copy import deepcopy
from functools import wraps

import torch
import transformers
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)
from transformers.integrations.deepspeed import is_deepspeed_zero3_enabled

from pinnacledb import logging
from pinnacledb.base.artifact import Artifact
from pinnacledb.base.build import build_datalayer
from pinnacledb.base.config import Config

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer
    from pinnacledb.ext.llm import LLM


class LLMCallback(TrainerCallback):
    def __init__(
        self,
        cfg: t.Optional["Config"] = None,
        identifier: t.Optional[str] = None,
        db: t.Optional["Datalayer"] = None,
        llm: t.Optional["LLM"] = None,
    ):
        self.cfg = cfg
        self.identifier = identifier
        self.db = db
        self.llm = llm

        # If we run training on remote, we need to provide identifier and cfg,
        # then can connect to db and load llm
        is_remote_init = self.identifier is not None and self.cfg is not None

        # If we run training on local, we can provide db and llm directly
        is_local_init = self.db is not None and self.llm is not None

        if not (is_remote_init or is_local_init):
            raise ValueError(
                "Please provide either (identifier and cfg) or (db and llm)"
            )

    def on_save(self, args, state, control, **kwargs):
        """Event called after a checkpoint save."""

        self.check_init()
        checkpoint_path = transformers.trainer.get_last_checkpoint(args.output_dir)
        if checkpoint_path is None:
            logging.warn("No checkpoint found, skip saving checkpoint")
            return

        self.llm.adapter_id = Artifact(checkpoint_path, serializer="zip")
        self.db.replace(self.llm, upsert=True)

    def check_init(self):
        # Rebuild datalayer for the new process
        if self.db is None:
            self.db = build_datalayer(self.cfg)
            self.llm = self.db.load("model", self.identifier)


@dc.dataclass
class LLMTrainingArguments(TrainingArguments):
    """
    LLM Training Arguments.
    Inherits from :class:`transformers.TrainingArguments`.

    {training_arguments_doc}
        lora_r (`int`, *optional*, defaults to 8):
            Lora R dimension.

        lora_alpha (`int`, *optional*, defaults to 16):
            Lora alpha.

        lora_dropout (`float`, *optional*, defaults to 0.05):
            Lora dropout.

        lora_target_modules (`List[str]`, *optional*, defaults to None):
            Lora target modules. If None, will be automatically inferred.

        lora_bias (`str`, *optional*, defaults to "none"):
            Lora bias.

        max_length (`int`, *optional*, defaults to 512):
            Maximum source sequence length during training.

    """

    use_lora: bool = True
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    lora_target_modules: t.Optional[t.List[str]] = None
    lora_bias: str = "none"
    bits: t.Optional[int] = None
    max_length: t.Optional[int] = 512
    on_ray: bool = False


def tokenize(tokenizer, example, X, y):
    prompt = example[X]

    prompt = prompt + tokenizer.eos_token
    result = tokenizer(
        prompt,
        truncation=True,
        max_length=tokenizer.model_max_length,
        padding="max_length",
    )
    result["labels"] = result["input_ids"].copy()
    return result


def train(
    training_args: LLMTrainingArguments,
    train_dataset,
    eval_datasets,
    model_kwargs,
    tokenizer_kwargs,
    X=None,
    y=None,
    db=None,
    llm=None,
    **kwargs,
):
    if X:
        tokenizer = AutoTokenizer.from_pretrained(
            **tokenizer_kwargs,
        )
        tokenizer.model_max_length = (
            training_args.max_length or tokenizer.model_max_length
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        train_dataset = train_dataset.map(
            lambda example: tokenize(tokenizer, example, X, y),
            remove_columns=[
                X,
            ],
        )

        if isinstance(eval_datasets, dict):
            eval_datasets = {
                k: v.map(
                    lambda example: tokenize(tokenizer, example, X, y),
                    remove_columns=[
                        X,
                    ],
                )
                for k, v in eval_datasets.items()
            }
        else:
            eval_datasets = eval_datasets.map(
                lambda example: tokenize(tokenizer, example, X, y),
                remove_columns=[
                    X,
                ],
            )

    if not training_args.on_ray:
        if db is not None and llm is not None:
            callbacks = [LLMCallback(db=db, llm=llm)]
        else:
            callbacks = None
        return train_func(
            training_args,
            train_dataset,
            eval_datasets,
            model_kwargs,
            tokenizer_kwargs,
            callbacks=callbacks,
            **kwargs,
        )

    else:
        if db is not None and llm is not None:
            from pinnacledb import CFG

            callbacks = [LLMCallback(cfg=CFG, identifier=llm.identifier)]
        else:
            callbacks = None
        # move the dataset logic here
        return ray_train(
            training_args,
            train_dataset,
            eval_datasets,
            model_kwargs=model_kwargs,
            tokenizer_kwargs=tokenizer_kwargs,
            callbacks=callbacks,
            **kwargs,
        )


def train_func(
    training_args: LLMTrainingArguments,
    train_dataset,
    eval_datasets,
    model_kwargs,
    tokenizer_kwargs,
    trainer_prepare_func=None,
    callbacks=None,
    **kwargs,
):
    model_kwargs = deepcopy(model_kwargs)
    tokenizer_kwargs = deepcopy(tokenizer_kwargs)
    # get device map
    device_map: t.Union[None, str, t.Dict[str, int]] = model_kwargs.get("device_map")
    if os.environ.get("LOCAL_RANK") is not None:
        ddp = int(os.environ.get("WORLD_SIZE", 1)) != 1
        device_map = {"": int(os.environ.get("LOCAL_RANK", "0"))} if ddp else None
    elif torch.backends.mps.is_available():
        device_map = "mps"

    quantization_config = create_quantization_config(training_args)

    if is_deepspeed_zero3_enabled():
        device_map = None
        model_kwargs["low_cpu_mem_usage"] = False
        if quantization_config is not None:
            raise ValueError(
                "Quantization is not supported with ZeRO-3. Please use ZeRO-2 instead."
            )

    logging.info("Overwriting model_kwargs for LLM training")
    logging.info(f"quantization_config: {quantization_config}")
    logging.info(f"device_map: {device_map}")

    model_kwargs["quantization_config"] = quantization_config
    model_kwargs["device_map"] = device_map
    model = AutoModelForCausalLM.from_pretrained(
        **model_kwargs,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        **tokenizer_kwargs,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.model_max_length = training_args.max_length or tokenizer.model_max_length

    if training_args.use_lora:
        model = prepare_lora_training(model, training_args)

    trainer = Trainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_datasets,
        **kwargs,
    )
    print("old trainer", trainer)
    if trainer_prepare_func is not None:
        trainer = trainer_prepare_func(trainer)
        print("new trainer", trainer)

    for callback in callbacks or []:
        trainer.add_callback(callback)
    trainer.model.config.use_cache = False
    trainer.train()
    trainer.save_state()


@wraps(train_func)
def ray_train(
    training_args: LLMTrainingArguments, train_dataset, eval_datasets, **kwargs
):
    import ray
    from ray import train
    from ray.train import RunConfig, ScalingConfig
    from ray.train.huggingface.transformers import (
        RayTrainReportCallback,
        prepare_trainer,
    )
    from ray.train.torch import TorchTrainer

    def trainer_prepare_func(trainer):
        trainer.add_callback(RayTrainReportCallback())
        trainer = prepare_trainer(trainer)
        return trainer

    def ray_train_func(train_loop_config):
        os.environ["OMP_NUM_THREADS"] = str(
            train.get_context().get_trial_resources().bundles[-1].get("CPU", 1)
        )
        ray_train_ds = train.get_dataset_shard("train")
        ray_eval_ds = train.get_dataset_shard("eval")

        train_ds_iterable = ray_train_ds.iter_torch_batches(batch_size=1)
        eval_ds_iterable = ray_eval_ds.iter_torch_batches(batch_size=1)

        # Create a new training_args object
        training_args = LLMTrainingArguments(**train_loop_config)
        kwargs["trainer_prepare_func"] = trainer_prepare_func
        return train_func(training_args, train_ds_iterable, eval_ds_iterable, **kwargs)

    ray_datasets = {
        "train": ray.data.from_huggingface(train_dataset),
        "eval": ray.data.from_huggingface(eval_datasets),
    }

    trainer = TorchTrainer(
        train_loop_per_worker=ray_train_func,
        # TODO: move this to a config
        scaling_config=ScalingConfig(
            num_workers=1,
            # use_gpu=False,
            # resources_per_worker={"GPU": 1},
        ),
        train_loop_config=training_args.to_dict(),
        datasets=ray_datasets,
        run_config=RunConfig(
            storage_path=os.path.abspath(training_args.output_dir),
        ),
    )

    results = trainer.fit()
    return results


def prepare_lora_training(model, config: LLMTrainingArguments):
    try:
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    except Exception as e:
        raise ImportError("Please install peft to use LoRA training") from e

    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        target_modules=config.lora_target_modules
        or get_lora_target_modules(model, config.bits),
        lora_dropout=config.lora_dropout,
        bias=config.lora_bias,
        task_type="CAUSAL_LM",
    )

    if config.bits:
        model = prepare_model_for_kbit_training(
            model,
            use_gradient_checkpointing=config.gradient_checkpointing,
        )

        ddp = int(os.environ.get("WORLD_SIZE", 1)) != 1
        if not ddp and torch.cuda.device_count() > 1:
            model.is_parallelizable = True
            model.model_parallel = True

    model = get_peft_model(model, lora_config)

    if config.gradient_checkpointing:
        model.enable_input_require_grads()

    if config.local_rank == 0:
        model.print_trainable_parameters()
    return model


def get_lora_target_modules(model, bits):
    try:
        import bitsandbytes as bnb
    except Exception as e:
        raise ImportError("Please install bitsandbytes to use LoRA training") from e

    if bits == 4:
        cls = bnb.nn.Linear4bit
    elif bits == 8:
        cls = bnb.nn.Linear8bitLt
    else:
        cls = torch.nn.Linear

    lora_module_names = set()
    for name, module in model.named_modules():
        if isinstance(module, cls):
            names = name.split(".")
            lora_module_names.add(names[0] if len(names) == 1 else names[-1])

    lora_module_names.discard("lm_head")
    return list(lora_module_names)


def create_quantization_config(config: LLMTrainingArguments):
    compute_dtype = (
        torch.float16
        if config.fp16
        else (torch.bfloat16 if config.bf16 else torch.float32)
    )
    if config.bits is not None:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=config.bits == 4,
            load_in_8bit=config.bits == 8,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
    else:
        quantization_config = None
    return quantization_config
