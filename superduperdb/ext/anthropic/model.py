import dataclasses as dc
import typing as t

import anthropic
from anthropic import APIConnectionError, APIError, APIStatusError, APITimeoutError

from pinnacledb.backends.ibis.data_backend import IbisDataBackend
from pinnacledb.backends.ibis.field_types import dtype
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.components.model import APIModel
from pinnacledb.ext.utils import format_prompt, get_key
from pinnacledb.misc.retry import Retry

retry = Retry(
    exception_types=(APIConnectionError, APIError, APIStatusError, APITimeoutError)
)

KEY_NAME = 'ANTHROPIC_API_KEY'


@dc.dataclass(kw_only=True)
class Anthropic(APIModel):
    """Anthropic predictor."""

    client_kwargs: t.Dict[str, t.Any] = dc.field(default_factory=dict)

    def __post_init__(self, artifacts):
        super().__post_init__(artifacts)
        self.identifier = self.identifier or self.model


@dc.dataclass(kw_only=True)
class AnthropicCompletions(Anthropic):
    """Cohere completions (chat) predictor.

    :param takes_context: Whether the model takes context into account.
    :param prompt: The prompt to use to seed the response.
    """

    prompt: str = ''

    def pre_create(self, db: Datalayer) -> None:
        super().pre_create(db)
        if isinstance(db.databackend, IbisDataBackend) and self.datatype is None:
            self.datatype = dtype('str')

    @retry
    def _predict_one(self, X, context: t.Optional[t.List[str]] = None, **kwargs):
        if context is not None:
            X = format_prompt(X, self.prompt, context=context)
        client = anthropic.Anthropic(api_key=get_key(KEY_NAME), **self.client_kwargs)
        resp = client.completions.create(prompt=X, model=self.identifier, **kwargs)
        return resp.completion

    @retry
    async def _apredict_one(self, X, context: t.Optional[t.List[str]] = None, **kwargs):
        if context is not None:
            X = format_prompt(X, self.prompt, context=context)
        client = anthropic.AsyncAnthropic(
            api_key=get_key(KEY_NAME), **self.client_kwargs
        )
        resp = await client.completions.create(
            prompt=X, model=self.identifier, **kwargs
        )
        return resp.completion

    def _predict(
        self, X, one: bool = True, context: t.Optional[t.List[str]] = None, **kwargs
    ):
        if context:
            assert one, 'context only works with ``one=True``'
        if one:
            return self._predict_one(X, context=context, **kwargs)
        return [self._predict_one(msg) for msg in X]

    async def _apredict(
        self, X, one: bool = True, context: t.Optional[t.List[str]] = None, **kwargs
    ):
        if context:
            assert one, 'context only works with ``one=True``'
        if one:
            return await self._apredict_one(X, context=context, **kwargs)
        return [await self._apredict_one(msg) for msg in X]
