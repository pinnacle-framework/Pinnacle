import typing as t

__all__ = ('pinnacle',)


class DuckTyper:
    attrs: t.Sequence[str]
    count: int = 0

    @classmethod
    def run(cls, item: t.Any, **kwargs):
        dts = [dt for dt in _DUCK_TYPES if dt.accept(item)]
        if len(dts) == 1:
            return dts[0].create(item, **kwargs)
        raise NotImplementedError(
            f'Couldn\'t auto-identify {item}, please wrap explicitly using '
            '``pinnacledb.core.*``'
        )

    @classmethod
    def accept(cls, item: t.Any) -> bool:
        count = cls.count or len(cls.attrs)
        return sum(hasattr(item, a) for a in cls.attrs) == count

    @classmethod
    def create(cls, item: t.Any, **kwargs) -> t.Any:
        raise NotImplementedError


class MongoDbTyper(DuckTyper):
    attrs = ('list_collection_names',)

    @classmethod
    def accept(cls, item: t.Any) -> bool:
        count = cls.count or len(cls.attrs)
        test_one = sum(hasattr(item, a) for a in cls.attrs) == count
        test_two = item.__class__.__name__ == 'Database'
        return test_one and test_two

    @classmethod
    def create(cls, item: t.Any, **kwargs) -> t.Any:
        from pymongo.database import Database

        from pinnacledb import CFG
        from pinnacledb.datalayer.base.build import build_vector_database
        from pinnacledb.datalayer.base.datalayer import Datalayer
        from pinnacledb.datalayer.mongodb.artifacts import MongoArtifactStore
        from pinnacledb.datalayer.mongodb.data_backend import MongoDataBackend
        from pinnacledb.datalayer.mongodb.metadata import MongoMetaDataStore

        if kwargs:
            raise ValueError('MongoDb creator accepts no parameters')
        if not isinstance(item, Database):
            raise TypeError('Expected Database but got {type(item)}')

        return Datalayer(
            databackend=MongoDataBackend(conn=item.client, name=item.name),
            metadata=MongoMetaDataStore(conn=item.client, name=item.name),
            artifact_store=MongoArtifactStore(
                conn=item.client, name=f'_filesystem:{item.name}'
            ),
            vector_database=build_vector_database(CFG.vector_search.type),
        )


class SklearnTyper(DuckTyper):
    attrs = '_predict', 'fit', 'score', 'transform'
    count = 2

    @classmethod
    def create(cls, item: t.Any, **kwargs) -> t.Any:
        from sklearn.base import BaseEstimator

        from pinnacledb.models.sklearn.wrapper import Estimator

        if not isinstance(item, BaseEstimator):
            raise TypeError('Expected BaseEstimator but got {type(item)}')

        kwargs['identifier'] = auto_identify(item)
        return Estimator(object=item, **kwargs)


class TorchTyper(DuckTyper):
    attrs = 'forward', 'parameters', 'state_dict', '_load_from_state_dict'

    @classmethod
    def create(cls, item: t.Any, **kwargs) -> t.Any:
        from torch import jit, nn

        from pinnacledb.models.torch.wrapper import TorchModel

        if isinstance(item, nn.Module) or isinstance(item, jit.ScriptModule):
            return TorchModel(identifier=auto_identify(item), object=item, **kwargs)

        raise TypeError('Expected a Module but got {type(item)}')


def auto_identify(instance):
    return instance.__class__.__name__.lower()


_DUCK_TYPES = MongoDbTyper, SklearnTyper, TorchTyper
pinnacle = DuckTyper.run
