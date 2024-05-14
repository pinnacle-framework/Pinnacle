import dataclasses as dc
import typing as t

from sentence_transformers import SentenceTransformer as _SentenceTransformer

from pinnacledb.backends.query_dataset import QueryDataset
from pinnacledb.base.code import Code
from pinnacledb.components.component import ensure_initialized
from pinnacledb.components.datatype import DataType, dill_lazy
from pinnacledb.components.model import Model, Signature, _DeviceManaged

DEFAULT_PREDICT_KWARGS = {
    'show_progress_bar': True,
}


@dc.dataclass(kw_only=True)
class SentenceTransformer(Model, _DeviceManaged):
    """A model for sentence embeddings using `sentence-transformers`.

    :param object: The SentenceTransformer object to use.
    :param model: The model name, e.g. 'all-MiniLM-L6-v2'.
    :param device: The device to use, e.g. 'cpu' or 'cuda'.
    :param preprocess: The preprocessing function to apply to the input.
    :param postprocess: The postprocessing function to apply to the output.
    :param signature: The signature of the model.
    """

    _artifacts: t.ClassVar[t.Sequence[t.Tuple[str, 'DataType']]] = (
        ('object', dill_lazy),
    )

    object: t.Optional[_SentenceTransformer] = None
    model: t.Optional[str] = None
    device: str = 'cpu'
    preprocess: t.Union[None, t.Callable, Code] = None
    postprocess: t.Union[None, t.Callable, Code] = None
    signature: Signature = 'singleton'

    ui_schema: t.ClassVar[t.List[t.Dict]] = [
        {'name': 'model', 'type': 'str', 'default': 'all-MiniLM-L6-v2'},
        {'name': 'device', 'type': 'str', 'default': 'cpu', 'choices': ['cpu', 'cuda']},
        {'name': 'predict_kwargs', 'type': 'json', 'default': DEFAULT_PREDICT_KWARGS},
        {'name': 'postprocess', 'type': 'code', 'default': Code.default},
    ]

    @classmethod
    def handle_integration(cls, kwargs):
        """Handle integration of the model."""
        if isinstance(kwargs.get('preprocess'), str):
            kwargs['preprocess'] = Code(kwargs['preprocess'])
        if isinstance(kwargs.get('postprocess'), str):
            kwargs['postprocess'] = Code(kwargs['postprocess'])
        return kwargs

    def __post_init__(self, artifacts):
        super().__post_init__(artifacts)

        if self.model is None:
            self.model = self.identifier

        if self.object is None:
            self.object = _SentenceTransformer(self.model, device=self.device)

    def init(self):
        """Initialize the model."""
        super().init()
        self.to(self.device)

    def to(self, device):
        """Move the model to a device.

        :param device: The device to move to, e.g. 'cpu' or 'cuda'.
        """
        self.object = self.object.to(device)
        self.object._target_device = device

    def _deep_flat_encode(self, cache):
        from pinnacledb.base.document import _deep_flat_encode

        r = dict(self.dict())
        r['dict'] = _deep_flat_encode(r['dict'], cache)
        r['id'] = self.id
        cache[self.id] = r
        del cache[r['dict']['object']]
        del r['dict']['object']
        assert 'object' not in r['dict']
        return self.id

    @ensure_initialized
    def predict_one(self, X, *args, **kwargs):
        """Predict on a single input.

        :param X: The input to predict on.
        :param args: Additional positional arguments, which are passed to the model.
        :param kwargs: Additional keyword arguments, which are passed to the model.
        """
        if self.preprocess is not None:
            X = self.preprocess(X)

        assert self.object is not None
        result = self.object.encode(X, *args, **{**self.predict_kwargs, **kwargs})
        if self.postprocess is not None:
            result = self.postprocess(result)
        return result

    @ensure_initialized
    def predict(self, dataset: t.Union[t.List, QueryDataset]) -> t.List:
        """Predict on a dataset.

        :param dataset: The dataset to predict on.
        """
        if self.preprocess is not None:
            dataset = list(map(self.preprocess, dataset))  # type: ignore[arg-type]
        assert self.object is not None
        results = self.object.encode(dataset, **self.predict_kwargs)
        if self.postprocess is not None:
            results = self.postprocess(results)  # type: ignore[operator]
        return results
