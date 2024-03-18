import dataclasses as dc
import typing as t

import networkx as nx

from pinnacledb import Schema
from pinnacledb.backends.query_dataset import QueryDataset
from pinnacledb.components.model import Signature, _Predictor


@dc.dataclass(kw_only=True)
class Graph(_Predictor):
    '''
    Represents a directed acyclic graph composed of interconnected model nodes.

    This class enables the creation of complex predictive models
    by defining a computational graph structure where each node
    represents a predictive model. Models can be connected via edges
    to define dependencies and flow of data.

    The predict() method executes predictions through the graph, ensuring
    correct data flow and handling of dependencies

    Example:
    >>  g = Graph(
    >>    identifier='simple-graph', input=model1, outputs=[model2], signature='*args'
    >>  )
    >>  g.connect(model1, model2)
    >>  assert g.predict_one(1) == [(4, 2)]

    '''

    models: t.List[_Predictor] = dc.field(default_factory=list)
    edges: t.List[t.Tuple[str, str, t.Tuple[t.Union[int, str], str]]] = dc.field(
        default_factory=list
    )
    input: _Predictor
    outputs: t.List[t.Union[str, _Predictor]] = dc.field(default_factory=list)
    _DEFAULT_ARG_WEIGHT: t.ClassVar[tuple] = (None, 'singleton')
    signature: Signature = '*args,**kwargs'
    type_id: t.ClassVar[str] = 'model'

    def __post_init__(self, artifacts):
        self.G = nx.DiGraph()
        self.nodes = {}
        self.version = 0
        self._db = None

        self.signature = self.input.signature
        self.output_identifiers = [
            o.identifier if isinstance(o, _Predictor) else o for o in self.outputs
        ]

        # Load the models and edges into a di graph
        models = {m.identifier: m for m in self.models}
        if self.edges and models:
            for connection in self.edges:
                u, v, on = connection
                self.connect(
                    models[u],
                    models[v],
                    on=on,
                    update_edge=False,
                )
        super().__post_init__(artifacts=artifacts)

    def connect(
        self,
        u: _Predictor,
        v: _Predictor,
        on: t.Optional[t.Tuple[t.Union[int, str], str]] = None,
        update_edge: t.Optional[bool] = True,
    ):
        '''
        Connects two nodes `u` and `v` on edge where edge is a tuple with
        first element describing outputs index (int or None)
        and second describing input argument (str).

        Note:
        output index: None means all outputs of node u are connected to node v
        '''
        assert isinstance(u, _Predictor)
        assert isinstance(v, _Predictor)

        if u.identifier not in self.nodes:
            self.nodes[u.identifier] = u
            self.G.add_node(u.identifier)

        if v.identifier not in self.nodes:
            self.nodes[v.identifier] = v
            self.G.add_node(v.identifier)

        G_ = self.G.copy()
        G_.add_edge(u.identifier, v.identifier, weight=on or self._DEFAULT_ARG_WEIGHT)
        if not nx.is_directed_acyclic_graph(G_):
            raise TypeError('The graph is not DAG with this edge')
        self.G = G_

        if update_edge:
            self.edges.append(
                (u.identifier, v.identifier, on or self._DEFAULT_ARG_WEIGHT)
            )
            if isinstance(u, _Predictor) and u not in self.models:
                self.models.append(u)
            if v not in self.models:
                self.models.append(v)
        return

    def fetch_output(
        self, output, index: t.Optional[t.Union[int, str]] = None, one: bool = False
    ):
        if index is not None:
            assert isinstance(index, (int, str))

            if isinstance(index, str):
                assert isinstance(
                    output, dict
                ), 'Output should be a dict for indexing with str'

            try:
                if one:
                    return output[index]
                else:
                    return [o[index] for o in output]

            except KeyError:
                raise KeyError("Model node does not have sufficient outputs")
        # Index None implies to pass all outputs to dependent node.
        return output

    def validate(self, node):
        '''
        Validates the graph for any disconnection
        '''
        # TODO: Create a cache to reduce redundant validation in predict in db

        predecessors = list(self.G.predecessors(node))
        dependencies = [self.validate(node=p) for p in predecessors]
        model = self.nodes[node]
        if dependencies and len(model.inputs) != len(dependencies):
            raise TypeError(
                f'Graph disconnected at Node: {model.identifier} '
                f'and is partially connected with {dependencies}\n'
                f'Required connected node is {len(model.inputs)} '
                f'but got only {len(dependencies)}, '
                f'Node required params: {model.inputs.params}'
            )
        return node

    def _fetch_inputs(self, dataset, edges=[], outputs=[], node=None):
        arg_inputs = []
        kwargs = {}
        node_signature = self.nodes[node].signature

        def _length(lst):
            count = 0
            for item in lst:
                if isinstance(item, (list, tuple)):
                    count += _length(item)
                else:
                    count += 1
            return count

        if not _length(outputs):
            outputs = dataset

        for ix, edge in enumerate(edges):
            output_key, input_key = edge['weight']
            arg_input_dataset = self.fetch_output(outputs[ix], output_key, one=False)
            if input_key == 'singleton':
                # If singleton we override input_key with actual model
                # singleton param.
                input_key = self.nodes[node].inputs.params[0]

            kwargs[input_key] = arg_input_dataset
            arg_inputs.append(arg_input_dataset)

        if not arg_inputs:
            return outputs

        batches = self._transpose(arg_inputs)
        mapped_dataset = []
        for batch in batches:
            batch = self._map_dataset_to_model(batch, node_signature, kwargs)
            mapped_dataset.append(batch)
        return mapped_dataset

    def _map_dataset_to_model(self, batch, signature, kwargs):
        if signature == '*args':
            return [[batch[p]] for p, _ in enumerate(kwargs)]
        elif signature == 'singleton':
            return batch[0]
        elif signature == '*args,**kwargs':
            return (), {k: batch[i] for i, k in enumerate(kwargs)}
        elif signature == '**kwargs':
            return {k: batch[i] for i, k in enumerate(kwargs)}

    def _fetch_input(self, args, kwargs, edges=[], outputs=[]):
        node_input = {}
        for ix, edge in enumerate(edges):
            output_key, input_key = edge['weight']

            node_input[input_key] = self.fetch_output(outputs[ix], output_key, one=True)
            kwargs = node_input
            args = ()

        if 'singleton' in node_input:
            args = (node_input['singleton'],)
            kwargs = {}
        return args, kwargs

    def _predict_on_node(self, *args, node=None, cache={}, one=True, **kwargs):
        if node not in cache:
            predecessors = list(self.G.predecessors(node))
            outputs = [
                self._predict_on_node(*args, **kwargs, one=one, node=p, cache=cache)
                for p in predecessors
            ]

            edges = [self.G.get_edge_data(p, node) for p in predecessors]

            if one is True:
                args, kwargs = self._fetch_input(
                    args, kwargs, edges=edges, outputs=outputs
                )
                cache[node] = self.nodes[node].predict_one(*args, **kwargs)
            else:
                dataset = self._fetch_inputs(
                    args[0], edges=edges, outputs=outputs, node=node
                )
                cache[node] = self.nodes[node].predict(dataset=dataset)
            return cache[node]
        return cache[node]

    def predict_one(self, *args, **kwargs):
        '''
        Single data point prediction passes the args and kwargs to defined node flow
        in the graph.
        '''
        # Validate the node for incompletion
        list(map(self.validate, self.output_identifiers))
        cache = {}

        outputs = [
            self._predict_on_node(*args, node=output, cache=cache, **kwargs)
            for output in self.output_identifiers
        ]

        # TODO: check if output schema and datatype required
        return outputs

    def patch_dataset_to_args(self, dataset):
        '''
        Patch the dataset with args type as default, since all
        corresponding nodes takes args as input type
        '''
        args_dataset = []
        signature = self.signature
        input_params = self.input.inputs

        def mapping(x, signature):
            if signature == '*args':
                return {p: d for d, p in zip(x, input_params.params)}
            elif signature == '*args,**kwargs':
                base_kwargs = x[1]
                kwargs = {a: d for a, d in zip(input_params.args, x[0])}
                return kwargs.update(base_kwargs)
            else:
                return x

        for data in dataset:
            data = mapping(data, signature)
            args_dataset.append(data)
        return args_dataset

    def predict(self, dataset: t.Union[t.List, QueryDataset]) -> t.List:
        # Validate the node for incompletion
        list(map(self.validate, self.output_identifiers))

        if isinstance(dataset, QueryDataset):
            raise TypeError('QueryDataset is not supported in graph mode')
        cache: t.Dict[str, t.Any] = {}

        outputs = [
            self._predict_on_node(dataset, node=output, cache=cache, one=False)
            for output in self.output_identifiers
        ]

        # TODO: check if output schema and datatype required
        return outputs

    def encode_outputs(self, outputs):
        encoded_outputs = []
        for o, n in zip(outputs, self.output_identifiers):
            encoded_outputs.append(self.nodes[n].encode_outputs(o))
        outputs = self._transpose(outputs=encoded_outputs or outputs)

        # Set the schema in runtime
        self.output_schema = Schema(
            identifier=self.identifier,
            fields={k.identifier: k.datatype for k in self.outputs},
        )

        return self.encode_with_schema(outputs)

    @staticmethod
    def _transpose(outputs):
        transposed_outputs = []
        for i in range(len(outputs[0])):
            batch_outs = []
            for o in outputs:
                batch_outs.append(o[i])
            transposed_outputs.append(batch_outs)

        return transposed_outputs
