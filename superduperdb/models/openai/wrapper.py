import os
import typing as t

import tqdm


from openai import ChatCompletion
from openai import Embedding
from openai import Model as OpenAIModel
from openai.error import Timeout, RateLimitError, TryAgain, ServiceUnavailableError

import pinnacledb as s
from pinnacledb.core.component import Component
from pinnacledb.misc.retry import Retry
from pinnacledb.misc import dataclasses as dc
from pinnacledb.misc.compat import cache
from pinnacledb.encoders.vectors.vector import vector


retry = Retry(
    exception_types=(RateLimitError, ServiceUnavailableError, Timeout, TryAgain)
)


def init_fn():
    s.log.info('Setting OpenAI api-key...')
    os.environ['OPENAI_API_KEY'] = s.CFG.apis.providers['openai'].api_key


@cache
def _available_models():
    return tuple([r['id'] for r in OpenAIModel.list()['data']])


@dc.dataclass
class OpenAI(Component):
    variety: t.ClassVar[str] = 'model'

    def __post_init__(self):
        if self.identifier not in (mo := _available_models()):
            msg = f'model {self.identifier} not in OpenAI available models, {mo}'
            raise ValueError(msg)

        if 'OPENAI_API_KEY' not in os.environ:
            raise ValueError('OPENAI_API_KEY not set')


@dc.dataclass
class OpenAIEmbedding(OpenAI):
    shapes = {'text-embedding-ada-002': (1536,)}

    def __init__(self, identifier: str, shape: t.Optional[t.Sequence[int]] = None):
        super().__init__(identifier)
        if shape is None:
            shape = self.shapes[identifier]
        self.encoder = vector(shape)

    @retry
    def _predict_one(self, X, **kwargs):
        e = Embedding.create(input=X, model=self.identifier, **kwargs)
        return e['data'][0]['embedding']

    @retry
    def _predict_a_batch(self, texts, **kwargs):
        out = Embedding.create(input=texts, model=self.identifier, **kwargs)['data']
        return [r['embedding'] for r in out]

    def _predict(self, X, batch_size=100, **kwargs):  # asyncio?
        if isinstance(X, str):
            return self._predict_one(X)
        out = []
        for i in tqdm.tqdm(range(0, len(X), batch_size)):
            out.extend(self._predict_a_batch(X[i : i + batch_size], **kwargs))
        return out


class OpenAIChatCompletion(OpenAI):
    @retry
    def predict_one(self, message, **kwargs):
        return ChatCompletion.create(
            messages=[{'role': 'user', 'content': message}],
            model=self.identifier,
            **kwargs,
        )['choices'][0]['message']['content']

    def predict(self, messages, **kwargs):
        return [self.predict_one(msg) for msg in messages]  # use asyncio
