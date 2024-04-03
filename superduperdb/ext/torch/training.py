import dataclasses as dc
import typing as t

import torch
from torch.utils.data import DataLoader

from pinnacledb import logging
from pinnacledb.backends.query_dataset import QueryDataset
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.components.dataset import Dataset
from pinnacledb.components.model import Trainer, _Fittable
from pinnacledb.ext.torch.model import TorchModel


@dc.dataclass(kw_only=True)
class TorchTrainer(Trainer):
    """
    Configuration for the PyTorch trainer.

    :param objective: Objective function
    :param loader_kwargs: Kwargs for the dataloader
    :param max_iterations: Maximum number of iterations
    :param no_improve_then_stop: Number of iterations to wait for improvement
                                 before stopping
    :param download: Whether to download the data
    :param validation_interval: How often to validate
    :param listen: Which metric to listen to for early stopping
    :param optimizer_cls: Optimizer class
    :param optimizer_kwargs: Kwargs for the optimizer
    :param optimizer_state: Latest state of the optimizer for contined training
    """

    objective: t.Callable
    loader_kwargs: t.Dict = dc.field(default_factory=dict)
    max_iterations: int = 10**100
    no_improve_then_stop: int = 5
    download: bool = False
    validation_interval: int = 100
    listen: str = 'objective'
    optimizer_cls: str = 'Adam'
    optimizer_kwargs: t.Dict = dc.field(default_factory=dict)
    optimizer_state: t.Optional[t.Dict] = None
    collate_fn: t.Optional[t.Callable] = None

    def get_optimizers(self, model):
        cls_ = getattr(torch.optim, self.optimizer_cls)
        optimizer = cls_(model.parameters(), **self.optimizer_kwargs)
        if self.optimizer_state is not None:
            self.optimizer.load_state_dict(self.optimizer_state)
            self.optimizer_state = None
        return (optimizer,)

    def _create_loader(self, dataset):
        return torch.utils.data.DataLoader(
            dataset,
            **self.loader_kwargs,
            collate_fn=self.collate_fn,
        )

    def fit(
        self,
        model: TorchModel,
        db: Datalayer,
        train_dataset: QueryDataset,
        valid_dataset: QueryDataset,
    ):
        train_dataloader = self._create_loader(train_dataset)
        valid_dataloader = self._create_loader(valid_dataset)
        return self._fit_with_dataloaders(
            model,
            db,
            train_dataloader=train_dataloader,
            valid_dataloader=valid_dataloader,
        )

    def take_step(self, model, batch, optimizers):
        if model.train_signature == '*args':
            outputs = model.train_forward(*batch)
        elif model.train_signature == 'singleton':
            outputs = model.train_forward(batch)
        elif model.train_signature == '**kwargs':
            outputs = model.train_forward(**batch)
        elif model.train_signature == '*args,**kwargs':
            outputs = model.train_forward(*batch[0], **batch[1])
        objective_value = self.objective(*outputs)
        for opt in optimizers:
            opt.zero_grad()
        objective_value.backward()
        for opt in optimizers:
            opt.step()
        return objective_value

    def compute_validation_objective(self, model, valid_dataloader):
        objective_values = []
        with model.evaluating(), torch.no_grad():
            for batch in valid_dataloader:
                objective_values.append(
                    self.objective(*model.train_forward(*batch)).item()
                )
            return sum(objective_values) / len(objective_values)

    def _fit_with_dataloaders(
        self,
        model,
        db: Datalayer,
        train_dataloader: DataLoader,
        valid_dataloader: DataLoader,
        validation_sets: t.Optional[t.Sequence[t.Union[str, Dataset]]] = None,
    ):
        if validation_sets is None:
            validation_sets = []
        model.train()
        iteration = 0

        optimizers = self.get_optimizers(model)

        while True:
            for batch in train_dataloader:
                train_objective = self.take_step(model, batch, optimizers)
                self.log(fold='TRAIN', iteration=iteration, objective=train_objective)

                if iteration % self.validation_interval == 0:
                    valid_loss = self.compute_validation_objective(
                        model, valid_dataloader
                    )
                    all_metrics = {}
                    for vs in validation_sets:
                        m = model.validate(vs)
                        all_metrics.update(m)
                    all_metrics.update({'objective': valid_loss})
                    _Fittable.append_metrics(model, all_metrics)
                    self.log(fold='VALID', iteration=iteration, **all_metrics)
                    if self.saving_criterion(model):
                        model.changed.add('object')
                        db.replace(model, upsert=True)
                        list(map(model.changed.add, ['all_metrics', 'optimizer_state']))
                    stop = self.stopping_criterion(iteration, model)
                    if stop:
                        return
                iteration += 1

    def stopping_criterion(self, iteration, model):
        max_iterations = self.max_iterations
        no_improve_then_stop = self.no_improve_then_stop
        if isinstance(max_iterations, int) and iteration >= max_iterations:
            return True
        if isinstance(no_improve_then_stop, int):
            if self.listen == 'objective':
                to_listen = [-x for x in model.metric_values['objective']]
            else:
                to_listen = model.metric_values[self.listen]

            if max(to_listen[-no_improve_then_stop:]) < max(to_listen):
                logging.info('early stopping triggered!')
                return True
        return False

    def saving_criterion(self, model):
        if self.listen == 'objective':
            to_listen = [-x for x in model.metric_values['objective']]
        else:
            to_listen = model.metric_values[self.listen]
        if all([to_listen[-1] >= x for x in to_listen[:-1]]):
            return True
        return False

    def log(self, **kwargs):
        out = ''
        for k, v in kwargs.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    out += f'{k}/{kk}: {vv}; '
            else:
                out += f'{k}: {v}; '
        logging.info(out)
