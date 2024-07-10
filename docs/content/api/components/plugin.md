**`pinnacle.components.plugin`** 

[Source code](https://github.com/pinnacle/pinnacle/blob/main/pinnacle.components/plugin.py)

## `Plugin` 

```python
Plugin(self,
     db: dataclasses.InitVar[typing.Optional[ForwardRef('Datalayer')]] = None,
     uuid: None = None,
     *,
     identifier: str = '',
     plugins: "t.Optional[t.List['Plugin']]" = None,
     artifacts: 'dc.InitVar[t.Optional[t.Dict]]' = None,
     path: str,
     cache_path: str = '.pinnacle/plugins') -> None
```
| Parameter | Description |
|-----------|-------------|
| identifier | Unique identifier for the plugin. |
| db | Datalayer instance. |
| uuid | UUID of the leaf. |
| artifacts | A dictionary of artifacts paths and `DataType` objects |
| plugins | A list of plugins to be used in the component. |
| path | Path to the plugin package or module. |
| cache_path | Path to the cache directory where the plugin will be stored. |

Plugin component allows to install and use external python packages as plugins.

