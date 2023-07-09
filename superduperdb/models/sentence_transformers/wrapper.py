import typing as t

from pinnacledb.core.model import Model


class SentenceTransformer(Model):
    def _predict(self, X: t.Union[str, t.List[str]], **kwargs):
        return self.object.encode(X, **kwargs)
