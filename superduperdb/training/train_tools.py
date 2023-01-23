import random
import time
import uuid
from collections import defaultdict

import pymongo
import torch.utils.data

from pinnacledb import client
from pinnacledb.models.utils import apply_model
from pinnacledb.training.loading import QueryDataset
from pinnacledb.utils import MongoStyleDict, progressbar
from pinnacledb.training.validation import validate_representations


class Trainer:
    def __init__(self,
                 train_name,
                 client,
                 database,
                 collection,
                 models,
                 keys,
                 model_names,
                 validation_sets=(),
                 metrics=None,
                 loss=None,
                 batch_size=100,
                 optimizers=(),
                 lr=0.0001,
                 num_workers=0,
                 projection=None,
                 filter=None,
                 features=None,
                 n_epochs=None,
                 n_iterations=None,
                 save=None,
                 watch='loss',
                 log_weights=False,
                 validation_interval=1000,
                 no_improve_then_stop=10,
                 download=False):

        self.id = uuid.uuid4()
        self.train_name = train_name
        self._client = client
        self._database = database
        self._collection = collection
        self._collection_object = None

        self.encoders = models
        self.keys = keys
        self.loss = loss
        self.features = features
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.filter = filter if filter is not None else {}
        self.valid_ids = [
            r['_id'] for r in self.collection.find({**self.filter, '_fold': 'valid'},
                                                   {'_id': 1}).sort('_id', pymongo.ASCENDING)
        ]
        self.validation_sets = validation_sets
        self.n_epochs = n_epochs
        self.n_iterations = n_iterations
        self.download = download
        self.training_id = str(int(time.time() * 100))
        self.projection = projection
        self.train_data = QueryDataset(
            client=self._client,
            database=self._database,
            collection=self._collection,
            filter={**self.filter, '_fold': 'train'},
            transform=self.apply_splitter_and_encoders,
            projection=self.projection,
            features=features,
        )
        self.valid_data = QueryDataset(
            client=self._client,
            database=self._database,
            collection=self._collection,
            filter={**self.filter, '_fold': 'valid'},
            download=True,
            transform=self.apply_splitter_and_encoders,
            projection=self.projection,
            features=features,
        )
        self.best = []
        self.metrics = metrics if metrics is not None else {}
        if isinstance(self.keys, str):  # pragma: no cover
            self.keys = (self.keys,)
        if not isinstance(self.encoders, tuple) and not isinstance(self.encoders, list):  # pragma: no cover
            self.encoders = [self.encoders,]
        self.encoders = list(self.encoders)
        self._send_to_device()
        self.learn_fields = self.keys
        self.learn_encoders = self.encoders
        if len(self.keys) == 1:
            self.learn_fields = (self.keys[0], self.keys[0])
            self.learn_encoders = (self.encoders[0], self.encoders[0])
        self.optimizers = optimizers if optimizers else [
            self._get_optimizer(encoder, lr) for encoder in self.encoders
            if isinstance(encoder, torch.nn.Module) and list(encoder.parameters())
        ]
        self.model_names = model_names
        self.watch = watch
        self.metric_values = defaultdict(lambda: [])
        self.lr = lr
        self.weights_dict = defaultdict(lambda: [])
        self._weights_choices = {}
        self._init_weight_traces()
        self._log_weights = log_weights
        self.save = save
        self.validation_interval = validation_interval
        self.no_improve_then_stop = no_improve_then_stop

    def _send_to_device(self):
        if not torch.cuda.is_available():
            return
        if torch.cuda.device_count() == 1:
            for m in self.encoders:
                if isinstance(m, torch.nn.Module):
                    m.to('cuda')
            return
        for i, m in enumerate(self.encoders):
            if isinstance(m, torch.nn.Module):
                self.encoders[i] = torch.nn.DataParallel(m)

    def _early_stop(self):
        if self.watch == 'loss':
            to_watch = [-x for x in self.metric_values['loss']]
        else:  # pragma: no cover
            to_watch = self.metric_values[self.watch]
        if max(to_watch[-self.no_improve_then_stop:]) < max(to_watch):  # pragma: no cover
            print('early stopping triggered!')
            return True
        return False

    def _save_weight_traces(self):
        self.collection[self.sub_collection].update_one(
            {'name': self.train_name},
            {'$set': {'weights': self.weights_dict}}
        )

    def _init_weight_traces(self):
        for i, e in enumerate(self.encoders):
            try:
                sd = e.state_dict()
            except AttributeError:
                continue
            self._weights_choices[i] = {}
            for p in sd:
                if len(sd[p].shape) == 2:
                    indexes = [
                        (random.randrange(sd[p].shape[0]), random.randrange(sd[p].shape[1]))
                        for _ in range(min(10, max(sd[p].shape[0], sd[p].shape[1])))
                    ]
                else:
                    assert len(sd[p].shape) == 1
                    indexes = [
                        (random.randrange(sd[p].shape[0]),)
                        for _ in range(min(10, sd[p].shape[0]))
                    ]
                self._weights_choices[i][p] = indexes

    def log_weight_traces(self):
        for i, f in enumerate(self._weights_choices):
            sd = self.encoders[i].state_dict()
            for p in self._weights_choices[f]:
                indexes = self._weights_choices[f][p]
                tmp = []
                for ind in indexes:
                    param = sd[p]
                    if len(ind) == 1:
                        tmp.append(param[ind[0]].item())
                    elif len(ind) == 2:
                        tmp.append(param[ind[0], ind[1]].item())
                    else:  # pragma: no cover
                        raise Exception('3d tensors not supported')
                self.weights_dict[f'{f}.{p}'].append(tmp)

    def _save_metrics(self):
        self.collection[self.sub_collection].update_one(
            {'name': self.train_name},
            {'$set': {'metric_values': self.metric_values, 'weights': self.weights_dict}}
        )

    def _save_best_model(self):
        agg = min if self.watch == 'loss' else max
        if self.watch == 'loss' and self.metric_values['loss'][-1] == agg(self.metric_values['loss']):
            print('saving')
            for sn, encoder in zip(self.model_names, self.encoders):
                self.save(sn, encoder)
        else:  # pragma: no cover
            print('no best model found...')

    def calibrate(self, encoder):
        if not hasattr(encoder, 'calibrate'):
            return
        raise NotImplementedError  # pragma: no cover

    @property
    def client(self):
        return client.SuperDuperClient(**self._client)

    @property
    def database(self):
        return self.client[self._database]

    @property
    def collection(self):
        if self._collection_object is None:
            self._collection_object = self.database[self._collection]
        return self._collection_object

    def _get_optimizer(self, encoder, lr):
        learnable_parameters = [x for x in encoder.parameters() if x.requires_grad]
        return torch.optim.Adam(learnable_parameters, lr=lr)

    def apply_splitter_and_encoders(self, sample):
        if hasattr(self, 'splitter') and self.splitter is not None:
            sample = self.splitter(sample)
        else:
            sample = [sample for _ in self.learn_fields]
        return _Mapped([
            x.preprocess if hasattr(x, 'preprocess') else lambda x: x
            for x in self.learn_encoders
        ], self.learn_fields)(sample)

    @property
    def data_loaders(self):
        return (
            torch.utils.data.DataLoader(self.train_data, batch_size=self.batch_size,
                                        num_workers=self.num_workers, shuffle=True),
            torch.utils.data.DataLoader(self.valid_data, batch_size=self.batch_size,
                                        num_workers=self.num_workers),
        )

    def log_progress(self, **kwargs):
        out = ''
        for k, v in kwargs.items():
            out += f'{k}: {v}; '
        print(out)

    @staticmethod
    def apply_models_to_batch(batch, models):
        output = []
        for subbatch, model in list(zip(batch, models)):
            output.append(model.forward(subbatch))
        return output

    def take_step(self, loss):
        for opt in self.optimizers:
            opt.zero_grad()
        loss.backward()
        for opt in self.optimizers:
            opt.step()
        if self._log_weights:
            self.log_weight_traces()
        return loss

    def validate_model(self, dataloader, model):
        raise NotImplementedError  # pragma: no cover

    def train(self):

        for encoder in self.encoders:
            self.calibrate(encoder)

        it = 0
        epoch = 0
        for m in self.encoders:
            if hasattr(m, 'eval'):
                m.eval()

        metrics = self.validate_model(self.data_loaders[1], -1)
        for k in metrics:
            self.metric_values[k].append(metrics[k])
        self.log_progress(fold='VALID', iteration=it, epoch=epoch, **metrics)

        while True:
            for m in self.encoders:
                if hasattr(m, 'train'):
                    m.train()

            train_loader, valid_loader = self.data_loaders

            for batch in train_loader:
                outputs = self.apply_models_to_batch(batch, self.learn_encoders)
                l_ = self.take_step(self.loss(*outputs))
                self.log_progress(fold='TRAIN', iteration=it, epoch=epoch, loss=l_.item())
                it += 1
                if it % self.validation_interval == 0:
                    metrics = self.validate_model(valid_loader, epoch)
                    for k in metrics:
                        self.metric_values[k].append(metrics[k])
                    self._save_weight_traces()
                    self._save_best_model()
                    self.log_progress(fold='VALID', iteration=it, epoch=epoch, **metrics)
                    self._save_metrics()
                    stop = self._early_stop()
                    if stop:  # pragma: no cover
                        return
                if self.n_iterations is not None and it >= self.n_iterations:
                    return

            epoch += 1  # pragma: no cover
            if self.n_epochs is not None and epoch >= self.n_epochs:  # pragma: no cover
                return


class ImputationTrainer(Trainer):

    sub_collection = '_imputations'

    def __init__(self, *args, inference_model=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.inference_model = inference_model if inference_model is not None else self.encoders[0]

    def validate_model(self, data_loader, *args, **kwargs):
        for e in self.encoders:
            if hasattr(e, 'eval'):
                e.eval()
        docs = list(self.collection.find(
            {**self.filter, '_fold': 'valid'},
            features=self.features,
        ))
        if self.keys[0] != '_base':
            inputs_ = [r[self.keys[0]] for r in docs]
        elif '_base' in self.features:
            inputs_ = [r['_base'] for r in docs]
        else:  # pragma: no cover
            inputs_ = docs

        if self.keys[1] != '_base':
            targets = [r[self.keys[1]] for r in docs]
        else:  # pragma: no cover
            targets = docs
        outputs = apply_model(
            self.inference_model,
            inputs_,
            single=False,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
        )
        metric_values = defaultdict(lambda: [])
        for o, t in zip(outputs, targets):
            for metric in self.metrics:
                metric_values[metric].append(self.metrics[metric](o, t))
        for batch in data_loader:
            outputs = self.apply_models_to_batch(batch, self.encoders)
            metric_values['loss'].append(self.loss(*outputs).item())

        for k in metric_values:
            metric_values[k] = sum(metric_values[k]) / len(metric_values[k])
        for e in self.encoders:
            if hasattr(e, 'train'):
                e.train()
        return metric_values


class _Mapped:
    def __init__(self, functions, keys):
        self.functions = functions
        self.keys = keys

    def __call__(self, args):
        args = [MongoStyleDict(r) for r in args]
        inputs = [r[k] for r, k in zip(args, self.keys)]
        return [f(i) for i, f in zip(inputs, self.functions)]


class RepresentationTrainer(Trainer):
    sub_collection = '_semantic_indexes'

    def __init__(self, *args, n_retrieve=100, splitter=None, **kwargs):
        self.n_retrieve = n_retrieve
        self.splitter = splitter
        super().__init__(*args, **kwargs)

    def validate_model(self, data_loader, epoch):
        results = {}
        for vs in self.validation_sets:
            results[vs] = validate_representations(self.collection, self.validation_set, self.train_name,
                                                   self.metrics, self.encoders, features=self.features,
                                                   refresh=True)
        loss_values = []
        for batch in data_loader:
            outputs = self.apply_models_to_batch(batch, self.learn_encoders)
            loss_values.append(self.loss(*outputs).item())
        results['loss'] = sum(loss_values) / len(loss_values)
        for m in self.encoders:
            if hasattr(m, 'train'):
                m.train()
        return results

