**`pinnacle.backends.local.artifacts`** 

[Source code](https://github.com/pinnacle/pinnacle/blob/main/pinnacle/backends/local/artifacts.py)

## `FileSystemArtifactStore` 

```python
FileSystemArtifactStore(self,
     conn: Any,
     name: Optional[str] = None)
```
| Parameter | Description |
|-----------|-------------|
| conn | root directory of the artifact store |
| name | subdirectory to use for this artifact store |

Abstraction for storing large artifacts separately from primary data.

