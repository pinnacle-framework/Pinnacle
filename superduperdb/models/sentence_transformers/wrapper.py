from typing import Optional

from sentence_transformers import SentenceTransformer as _SentenceTransformer

from pinnacledb.core.model import Model


class SentenceTransformer(Model):
    def __init__(
        self,
        model_name_or_path: Optional[str] = None,
        identifier: Optional[str] = None,
    ):
        if identifier is None:
            identifier = model_name_or_path
        sentence_transformer = _SentenceTransformer(model_name_or_path)
        super().__init__(sentence_transformer, identifier)

    def predict_one(self, sentence, **kwargs):
        return self.object.encode(sentence)

    def predict(self, sentences, **kwargs):
        return self.object.encode(sentences)
