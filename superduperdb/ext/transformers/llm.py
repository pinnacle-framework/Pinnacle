import dataclasses as dc
import typing
import typing as t

from pinnacledb.misc.annotations import requires_packages

requires_packages(['transformers', '4.29.1'])

import transformers
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    pipeline,
)
from transformers.pipelines.text_generation import ReturnType

from pinnacledb import logging
from pinnacledb.backends.query_dataset import QueryDataset
from pinnacledb.components.component import ensure_initialized
from pinnacledb.components.datatype import DataType, dill_serializer
from pinnacledb.components.model import _Fittable, _Validator
from pinnacledb.ext.llm.base import BaseLLM
from pinnacledb.ext.transformers.llm_training import Checkpoint

if typing.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer


@dc.dataclass(kw_only=True)
class LLM(BaseLLM, _Fittable, _Validator):
    """
    LLM model based on `transformers` library.

    :param identifier: model identifier
    :param model_name_or_path: model name or path
    :param bits: quantization bits, [4, 8], default is None
    :param adapter_id: adapter id, default is None
        Add a adapter to the base model for inference.
        When model_name_or_path, bits, model_kwargs, tokenizer_kwargs are the same,
        will share the same base model and tokenizer cache.
    :param model_kwargs: model kwargs,
        all the kwargs will pass to `transformers.AutoModelForCausalLM.from_pretrained`
    :param tokenizer_kwagrs: tokenizer kwargs,
        all the kwargs will pass to `transformers.AutoTokenizer.from_pretrained`
    :param prompt_template: prompt template, default is "{input}"
    :param prompt_func: prompt function, default is None
    """

    identifier: str = ""
    model_name_or_path: t.Optional[str] = None
    adapter_id: t.Optional[t.Union[str, Checkpoint]] = None
    object: t.Optional[transformers.Trainer] = None
    model_kwargs: t.Dict = dc.field(default_factory=dict)
    tokenizer_kwargs: t.Dict = dc.field(default_factory=dict)
    prompt_func: t.Optional[t.Callable] = None
    training_kwargs: t.Dict = dc.field(default_factory=dict)

    # Save models and tokenizers cache for sharing when using multiple models
    _model_cache: t.ClassVar[dict] = {}
    _tokenizer_cache: t.ClassVar[dict] = {}

    _artifacts: t.ClassVar[t.Sequence[t.Tuple[str, DataType]]] = (
        ("model_kwargs", dill_serializer),
        ("tokenizer_kwargs", dill_serializer),
    )

    def __post_init__(self, artifacts):
        if not self.identifier:
            self.identifier = self.adapter_id or self.model_name_or_path

        #  TODO: Compatible with the bug of artifact sha1 equality and will be deleted
        self.tokenizer_kwargs.setdefault(
            "pretrained_model_name_or_path", self.model_name_or_path
        )

        super().__post_init__(artifacts)

    @classmethod
    def from_pretrained(
        cls,
        model_name_or_path,
        identifier="",
        prompt="{input}",
        prompt_func=None,
        **kwargs,
    ):
        """
        A new function to create a LLM model from from_pretrained function.
        Allow the user to directly replace:
        AutoModelForCausalLM.from_pretrained -> LLM.from_pretrained
        """
        model_kwargs = kwargs.copy()
        tokenizer_kwargs = {}
        return cls(
            model_name_or_path=model_name_or_path,
            identifier=identifier,
            model_kwargs=model_kwargs,
            tokenizer_kwargs=tokenizer_kwargs,
            prompt=prompt,
            prompt_func=prompt_func,
        )

    def init_pipeline(
        self, adapter_id: t.Optional[str] = None, load_adapter_directly: bool = False
    ):
        # Do not update model state here
        model_kwargs = self.model_kwargs.copy()
        tokenizer_kwargs = self.tokenizer_kwargs.copy()

        if self.model_name_or_path and not load_adapter_directly:
            model_kwargs["pretrained_model_name_or_path"] = self.model_name_or_path
            model = AutoModelForCausalLM.from_pretrained(
                **model_kwargs,
            )

            if adapter_id is not None:
                logging.info(f"Loading adapter from {adapter_id}")

                from peft import PeftModel

                try:
                    model = PeftModel.from_pretrained(
                        model, adapter_id, adapter_name=self.identifier
                    )
                except Exception as e:
                    message = (
                        f'Failed to add adapter to model, error: {e}\n'
                        'Try to load adapter directly\n'
                    )
                    logging.warn(message)
                    logging.warn("Try to load adapter directly")
                    return self.init_pipeline(adapter_id, load_adapter_directly=True)

                tokenizer_kwargs["pretrained_model_name_or_path"] = adapter_id

            else:
                tokenizer_kwargs[
                    "pretrained_model_name_or_path"
                ] = self.model_name_or_path

            tokenizer = AutoTokenizer.from_pretrained(
                **tokenizer_kwargs,
            )
        elif adapter_id is not None:
            model_kwargs['pretrained_model_name_or_path'] = adapter_id
            from peft import AutoPeftModelForCausalLM

            model = AutoPeftModelForCausalLM.from_pretrained(
                **model_kwargs,
            )
            tokenizer_kwargs["pretrained_model_name_or_path"] = adapter_id
            tokenizer = AutoTokenizer.from_pretrained(
                **tokenizer_kwargs,
            )

        else:
            raise ValueError(
                "model_name_or_path or adapter_id must be provided, "
                f"got {self.model_name_or_path} and {adapter_id} instead."
            )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        return pipeline("text-generation", model=model, tokenizer=tokenizer)

    def init(self):
        db = self.db

        real_adapter_id = None
        if self.adapter_id is not None:
            self.handle_chekpoint(db)
            if isinstance(self.adapter_id, Checkpoint):
                checkpoint = self.adapter_id
                self.adapter_id = checkpoint.uri

            elif isinstance(self.adapter_id, str):
                real_adapter_id = self.adapter_id
                checkpoint = None
            else:
                raise ValueError(
                    "adapter_id must be either a string or Checkpoint object, but got "
                    f"{type(self.adapter_id)}"
                )

            if checkpoint:
                db = db or checkpoint.db
                assert db, "db must be provided when using checkpoint indetiifer"
                if self.db is None:
                    self.db = db
                real_adapter_id = checkpoint.path.unpack(db)

        super().init()

        self.pipeline = self.init_pipeline(real_adapter_id)

    def handle_chekpoint(self, db):
        if isinstance(self.adapter_id, str):
            # match checkpoint://<identifier>/<version>
            if Checkpoint.check_uri(self.adapter_id):
                assert db, "db must be provided when using checkpoint indetiifer"
                identifier, version = Checkpoint.parse_uri(self.adapter_id)
                version = int(version)
                checkpoint = db.load("checkpoint", identifier, version=version)
                assert checkpoint, f"Checkpoint {self.adapter_id} not found"
                self.adapter_id = checkpoint

    @ensure_initialized
    def predict_one(self, X, context=None, **kwargs):
        X = self._process_inputs(X, context=context, **kwargs)
        results = self._batch_generate([X], **kwargs)
        return results[0]

    @ensure_initialized
    def predict(self, dataset: t.Union[t.List, QueryDataset], **kwargs) -> t.List:
        dataset = [
            self._process_inputs(dataset[i], **kwargs) for i in range(len(dataset))
        ]
        kwargs.pop("context", None)
        return self._batch_generate(dataset, **kwargs)

    def _process_inputs(self, X: t.Any, **kwargs) -> str:
        if isinstance(X, str):
            X = self.prompter(X, **kwargs)
        return X

    def _batch_generate(self, prompts: t.List[str], **kwargs) -> t.List[str]:
        """
        Generate text.
        Can overwrite this method to support more inference methods.
        """
        kwargs = {**self.predict_kwargs, **kwargs}

        # Set default values, if not will cause bad output
        kwargs.setdefault("add_special_tokens", True)
        kwargs.setdefault(
            "max_new_tokens", self.predict_kwargs.get("max_new_tokens", 256)
        )
        outputs = self.pipeline(
            prompts,
            return_type=ReturnType.NEW_TEXT,
            eos_token_id=self.pipeline.tokenizer.eos_token_id,
            pad_token_id=self.pipeline.tokenizer.eos_token_id,
            **{**self.predict_kwargs, **kwargs},
        )
        results = [output[0]["generated_text"] for output in outputs]
        return results

    def add_adapter(self, model_id, adapter_name: str):
        # TODO: Support lora checkpoint from s3
        try:
            from peft import PeftModel
        except Exception as e:
            raise ImportError("Please install peft to use LoRA training") from e

        logging.info(f"Loading adapter {adapter_name} from {model_id}")

        if not hasattr(self, "model"):
            self.init()

        if not isinstance(self.model, PeftModel):
            self.model = PeftModel.from_pretrained(
                self.model, model_id, adapter_name=adapter_name
            )
            # Update cache model
            self._model_cache[hash(self.model_kwargs)] = self.model
        else:
            # TODO where does this come from?
            self.model.load_adapter(model_id, adapter_name)

    def post_create(self, db: "Datalayer") -> None:
        # TODO: Do not make sense to add this logic here,
        # Need a auto DataType to handle this
        from pinnacledb.backends.ibis.data_backend import IbisDataBackend
        from pinnacledb.backends.ibis.field_types import dtype

        if isinstance(db.databackend, IbisDataBackend) and self.datatype is None:
            self.datatype = dtype("str")
        super().post_create(db)
