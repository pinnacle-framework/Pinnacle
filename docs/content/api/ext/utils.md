**`pinnacledb.ext.utils`** 

[Source code](https://github.com/SuperDuperDB/pinnacledb/blob/main/pinnacledb/ext/utils.py)

## `str_shape` 

```python
str_shape(shape: Sequence[int]) -> str
```
| Parameter | Description |
|-----------|-------------|
| shape | The shape to convert. |

Convert a shape to a string.

## `format_prompt` 

```python
format_prompt(X: str,
     prompt: str,
     context: Optional[List[str]] = None) -> str
```
| Parameter | Description |
|-----------|-------------|
| X | The input to format the prompt with. |
| prompt | The prompt to format. |
| context | The context to format the prompt with. |

Format a prompt with the given input and context.

## `get_key` 

```python
get_key(key_name: str) -> str
```
| Parameter | Description |
|-----------|-------------|
| key_name | The name of the environment variable to get. |

Get an environment variable.

## `pinnacledecode` 

```python
pinnacledecode(r: Any,
     encoders: Union[Dict[str,
     ForwardRef('DataType')],
     ForwardRef('LoadDict')])
```
| Parameter | Description |
|-----------|-------------|
| r | The object to decode. |
| encoders | The encoders to use. |

Decode a pinnacle encoded object.

## `pinnacleencode` 

```python
pinnacleencode(object)
```
| Parameter | Description |
|-----------|-------------|
| object | The object to encode. |

Encode an object using pinnacle.

