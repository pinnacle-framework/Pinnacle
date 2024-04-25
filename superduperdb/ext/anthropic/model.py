import dataclasses as dc
import typing as t

import anthropic
from anthropic import APIConnectionError, APIError, APIStatusError, APITimeoutError

from pinnacledb.backends.ibis.data_backend import IbisDataBackend
from pinnacledb.backends.ibis.field_types import dtype
from pinnacledb.backends.query_dataset import QueryDataset
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.components.model import APIBaseModel
from pinnacledb.ext.utils import format_prompt, get_key
from pinnacledb.misc.retry import Retry

retry = Retry(
    exception_types=(APIConnectionError, APIError, APIStatusError, APITimeoutError)
)

KEY_NAME = 'ANTHROPIC_API_KEY'


@dc.dataclass(kw_only=True)
class Anthropic(APIBaseModel):
    """Anthropic predictor."""

    client_kwargs: t.Dict[str, t.Any] = dc.field(default_factory=dict)

    def __post_init__(self, artifacts):
        self.model = self.model or self.identifier
        super().__post_init__(artifacts)
        self.client = anthropic.Anthropic(
            api_key=get_key(KEY_NAME), **self.client_kwargs
        )


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
    def predict_one(
        self,
        X: t.Union[str, list[dict]],
        context: t.Optional[t.List[str]] = None,
        **kwargs,
    ):
        if isinstance(X, str):
            if context is not None:
                X = format_prompt(X, self.prompt, context=context)
            messages = [{'role': 'user', 'content': X}]

        elif isinstance(X, list) and all(isinstance(p, dict) for p in X):
            messages = X

        else:
            raise ValueError(
                f'Invalid input: {X}, only support str or messages format data'
            )
        message = self.client.messages.create(
            messages=messages,
            model=self.model,
            **{**self.predict_kwargs, **kwargs},
        )
        return message.content[0].text

    def predict(self, dataset: t.Union[t.List, QueryDataset]) -> t.List:
        return [self.predict_one(dataset[i]) for i in range(len(dataset))]
