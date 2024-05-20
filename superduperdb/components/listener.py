import dataclasses as dc
import typing as t

from overrides import override

from pinnacledb import CFG
from pinnacledb.backends.base.query import Query
from pinnacledb.base.datalayer import Datalayer
from pinnacledb.base.document import _OUTPUTS_KEY
from pinnacledb.components.model import Mapping
from pinnacledb.misc.annotations import public_api
from pinnacledb.misc.server import request_server
from pinnacledb.rest.utils import parse_query

from ..jobs.job import Job
from .component import Component, ComponentTuple
from .model import Model, ModelInputType

if t.TYPE_CHECKING:
    from pinnacledb.base.datalayer import Datalayer


SELECT_TEMPLATE = {'documents': [], 'query': '<collection_name>.find()'}


@public_api(stability='stable')
@dc.dataclass(kw_only=True)
class Listener(Component):
    """Listener component.

    Listener object which is used to process a column/key of a collection or table,
    and store the outputs.

    :param key: Key to be bound to the model.
    :param model: Model for processing data.
    :param select: Object for selecting which data is processed.
    :param active: Toggle to ``False`` to deactivate change data triggering.
    :param predict_kwargs: Keyword arguments to self.model.predict().
    :param identifier: A string used to identify the model.
    """

    __doc__ = __doc__.format(component_parameters=Component.__doc__)

    ui_schema: t.ClassVar[t.List[t.Dict]] = [
        {'name': 'identifier', 'type': 'str', 'default': ''},
        {'name': 'key', 'type': 'json'},
        {'name': 'model', 'type': 'component/model'},
        {'name': 'select', 'type': 'json', 'default': SELECT_TEMPLATE},
        {'name': 'active', 'type': 'bool', 'default': True},
        {'name': 'predict_kwargs', 'type': 'json', 'default': {}},
    ]

    key: ModelInputType
    model: Model
    select: Query
    active: bool = True
    predict_kwargs: t.Optional[t.Dict] = dc.field(default_factory=dict)
    identifier: str = ''

    type_id: t.ClassVar[str] = 'listener'

    @classmethod
    def handle_integration(cls, kwargs):
        """Method to handle integration.

        :param kwargs: Integration keyword arguments.
        """
        if 'select' in kwargs and isinstance(kwargs['select'], dict):
            kwargs['select'] = parse_query(
                query=kwargs['select']['query'],
                documents=kwargs['select']['documents'],
            )
        return kwargs

    def __post_init__(self, db, artifacts):
        if self.identifier == '':
            self.identifier = self.id
        super().__post_init__(db, artifacts)

    @property
    def id(self):
        return f'component/{self.type_id}/{self.model.identifier}/{self.uuid}'

    @property
    def mapping(self):
        """Mapping property."""
        return Mapping(self.key, signature=self.model.signature)

    @property
    def outputs(self):
        """Get reference to outputs of listener model."""
        return f'{_OUTPUTS_KEY}.{self.uuid}'

    @property
    def outputs_select(self):
        """Get query reference to model outputs."""
        return self.select.table_or_collection.outputs(self.id)

        else:
            from pinnacledb.backends.mongodb.query import Collection

            model_update_kwargs = self.model.model_update_kwargs or {}
            if model_update_kwargs.get('document_embedded', True):
                collection_name = self.select.table_or_collection.identifier
            else:
                collection_name = self.outputs

            return Collection(collection_name).find()

    @property
    def outputs_key(self):
        """Model outputs key."""
        if self.select.DB_TYPE == "SQL":
            return 'output'
        else:
            return self.outputs

    @override
    def post_create(self, db: "Datalayer") -> None:
        """Post-create hook.

        :param db: Data layer instance.
        """
        output_table = db.databackend.create_output_dest(
            self.uuid,
            self.model.datatype,
            flatten=self.model.flatten,
        )
        if output_table is not None:
            db.add(output_table)
        if self.select is not None and self.active and not db.server_mode:
            if CFG.cluster.cdc.uri:
                request_server(
                    service='cdc',
                    endpoint='listener/add',
                    args={'name': self.identifier},
                    type='get',
                )
            else:
                db.cdc.add(self)

    @classmethod
    def create_output_dest(cls, db: "Datalayer", predict_id, model: Model):
        """
        Create output destination.

        :param db: Data layer instance.
        :param predict_id: Predict ID.
        :param model: Model instance.
        """
        if model.datatype is None:
            return
        output_table = db.databackend.create_output_dest(
            predict_id,
            model.datatype,
            flatten=model.flatten,
        )
        if output_table is not None:
            db.add(output_table)

    @property
    def dependencies(self) -> t.List[ComponentTuple]:
        """Listener model dependencies."""
        args, kwargs = self.mapping.mapping
        all_ = list(args) + list(kwargs.values())
        out = []
        for x in all_:
            if x.startswith('_outputs.'):
                listener_id = x.split('.')[1]
                out.append(listener_id)
        return out

    def depends_on(self, other: Component):
        """Check if the listener depends on another component.

        :param other: Another component.
        """
        if not isinstance(other, Listener):
            return False

        args, kwargs = self.mapping.mapping
        all_ = list(args) + list(kwargs.values())

        return any([x.startswith(f'_outputs.{other.uuid}') for x in all_])

    @override
    def schedule_jobs(
        self,
        db: "Datalayer",
        dependencies: t.Sequence[Job] = (),
        overwrite: bool = False,
    ) -> t.Sequence[t.Any]:
        """Schedule jobs for the listener.

        :param db: Data layer instance to process.
        :param dependencies: A list of dependencies.
        """
        if not self.active:
            return []
        assert not isinstance(self.model, str)

        out = [
            self.model.predict_in_db_job(
                X=self.key,
                db=db,
                predict_id=self.uuid,
                select=self.select,
                dependencies=dependencies,
                overwrite=overwrite,
                **(self.predict_kwargs or {}),
            )
        ]
        return out

    def cleanup(self, database: "Datalayer") -> None:
        """Clean up when the listener is deleted.

        :param database: Data layer instance to process.
        """
        # TODO - this doesn't seem to do anything
        if (cleanup := getattr(self.select, 'model_cleanup', None)) is not None:
            assert not isinstance(self.model, str)
            cleanup(database, model=self.model.identifier, key=self.key)
