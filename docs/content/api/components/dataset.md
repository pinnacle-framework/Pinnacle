**`pinnacle.components.dataset`** 

[Source code](https://github.com/pinnacle/pinnacle/blob/main/pinnacle.components/dataset.py)

## `Dataset` 

```python
Dataset(self,
     identifier: str,
     db: dataclasses.InitVar[typing.Optional[ForwardRef('Datalayer')]] = None,
     uuid: None = None,
     *,
     upstream: "t.Optional[t.List['Component']]" = None,
     artifacts: 'dc.InitVar[t.Optional[t.Dict]]' = None,
     select: 't.Optional[Query]' = None,
     sample_size: 't.Optional[int]' = None,
     random_seed: 't.Optional[int]' = None,
     creation_date: 't.Optional[str]' = None,
     raw_data: 't.Optional[t.Sequence[t.Any]]' = None,
     pin: 'bool' = False) -> None
```
| Parameter | Description |
|-----------|-------------|
| identifier | Identifier of the leaf. |
| db | Datalayer instance. |
| uuid | UUID of the leaf. |
| artifacts | A dictionary of artifacts paths and `DataType` objects |
| select | A query to select the documents for the dataset. |
| sample_size | The number of documents to sample from the query. |
| random_seed | The random seed to use for sampling. |
| creation_date | The date the dataset was created. |
| raw_data | The raw data for the dataset. |
| pin | Whether to pin the dataset. If True, the dataset will load the datas from the database every time. If False, the dataset will cache the datas after we apply to db. |

A dataset is an immutable collection of documents.

## `DataInit` 

```python
DataInit(self,
     identifier: str,
     db: dataclasses.InitVar[typing.Optional[ForwardRef('Datalayer')]] = None,
     uuid: None = None,
     *,
     upstream: "t.Optional[t.List['Component']]" = None,
     artifacts: 'dc.InitVar[t.Optional[t.Dict]]' = None,
     data: 't.List[t.Dict]',
     table: 'str') -> None
```
| Parameter | Description |
|-----------|-------------|
| identifier | Identifier of the leaf. |
| db | Datalayer instance. |
| uuid | UUID of the leaf. |
| artifacts | A dictionary of artifacts paths and `DataType` objects |

DataInit(identifier: str, db: dataclasses.InitVar[typing.Optional[ForwardRef('Datalayer')]] = None, uuid: None = None, *, upstream: "t.Optional[t.List['Component']]" = None, artifacts: 'dc.InitVar[t.Optional[t.Dict]]' = None, data: 't.List[t.Dict]', table: 'str')

