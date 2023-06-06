from typing import Optional

from pinnacledb.core.model import Model
from transformers import pipeline as _pipeline, Pipeline as TransformersPipeline


class Pipeline(Model):
    def __init__(
        self,
        pipeline: Optional[TransformersPipeline] = None,
        task: Optional[str] = None,
        model: Optional[str] = None,
        identifier: Optional[str] = None,
    ):
        if pipeline is None:
            assert model is not None, 'must specify model for now'
            pipeline = _pipeline(task, model=model)

        identifier = identifier or f'{pipeline.task}/{pipeline.model.name_or_path}'

        super().__init__(pipeline, identifier=identifier)

    def predict_one(self, r, **kwargs):
        return self.object(r, **kwargs)

    def predict(self, docs, **kwargs):
        return self.object(docs, **kwargs)


class TokenizingFunction:
    def __init__(self, tokenizer, **kwargs):
        self.tokenizer = tokenizer
        self.kwargs = kwargs

    def __call__(self, sentence):
        return self.tokenizer(sentence, batch=False, **self.kwargs)
