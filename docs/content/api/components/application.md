**`pinnacledb.components.application`** 

[Source code](https://github.com/SuperDuperDB/pinnacledb/blob/main/pinnacledb/components/application.py)

## `Application` 

```python
Application(self,
     identifier: str,
     db: dataclasses.InitVar[typing.Optional[ForwardRef('Datalayer')]] = None,
     uuid: str = <factory>,
     *,
     artifacts: 'dc.InitVar[t.Optional[t.Dict]]' = None,
     template: Union[pinnacledb.components.template.Template,
     str] = None,
     kwargs: Dict) -> None
```
| Parameter | Description |
|-----------|-------------|
| identifier | Identifier of the leaf. |
| db | Datalayer instance. |
| uuid | UUID of the leaf. |
| artifacts | A dictionary of artifacts paths and `DataType` objects |
| template | Template. |
| kwargs | Keyword arguments passed to `template`. |

Application built from template.

