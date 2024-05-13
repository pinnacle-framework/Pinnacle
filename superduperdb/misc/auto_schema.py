import importlib
import typing as t

from pinnacledb import logging
from pinnacledb.components.datatype import (
    DataType,
    DataTypeFactory,
    dill_decode,
    dill_encode,
    json_serializer,
)
from pinnacledb.components.schema import Schema


def register_module(module_name):
    """
    Register a module for datatype inference.
    Only modules with a check and create function will be registered

    """
    try:
        importlib.import_module(module_name)
    except Exception:
        logging.debug(f"Could not register module: {module_name}")


register_module("pinnacledb.ext.numpy.encoder")
register_module("pinnacledb.ext.torch.encoder")


DEFAULT_DATATYPE = DataType(
    "DEFAULT",
    encoder=dill_encode,
    decoder=dill_decode,
    encodable="encodable",
)

BASE_TYPES = (
    int,
    str,
    float,
    bool,
    bytes,
    bytearray,
)


def infer_datatype(data: t.Any) -> t.Optional[t.Union[DataType, type]]:
    """
    Infer the datatype of a given data object
    If the data object is a base type, return None,
    Otherwise, return the inferred datatype

    :param data: The data object
    """

    datatype = None

    if isinstance(data, BASE_TYPES):
        datatype = type(data)
        logging.info(f"Inferred base type: {datatype} for data:", data)
        return datatype

    for factory in DataTypeFactory.__subclasses__():
        if factory.check(data):
            datatype = factory.create(data)
            assert isinstance(datatype, DataType)
            logging.info(f"Inferred datatype: {datatype.identifier} for data: {data}")
            break

    if datatype is None:
        logging.info(f"Could not infer datatype for data: {data}, using default")
        datatype = DEFAULT_DATATYPE

    return datatype


def infer_schema(
    data: t.Mapping[str, t.Any],
    identifier: t.Optional[str] = None,
    ibis=False,
) -> Schema:
    """
    Infer a schema from a given data object

    :param data: The data object
    :param identifier: The identifier for the schema, if None, it will be generated
    :return: The inferred schema
    """

    assert isinstance(data, dict), "Data must be a dictionary"

    schema_data = {}
    for k, v in data.items():
        data_type = infer_datatype(v)
        if data_type is not None:
            schema_data[k] = data_type

    if ibis:
        schema_data = updated_schema_data_for_ibis(schema_data)
    else:
        schema_data = updated_schema_data_for_mongodb(schema_data)

    if identifier is None:
        if not schema_data:
            identifier = "empty"
        else:
            key_value_pairs = []
            for k, v in sorted(schema_data.items()):
                if hasattr(v, "identifier"):
                    key_value_pairs.append(f"{k}={v.identifier}")
                else:
                    key_value_pairs.append(f"{k}={str(v)}")
            identifier = "&".join(key_value_pairs)

    if identifier is None:
        raise ValueError("Could not infer schema identifier")

    return Schema(identifier=identifier, fields=schema_data)  # type: ignore


def updated_schema_data_for_ibis(
    schema_data,
) -> t.Dict[str, DataType]:
    from pinnacledb.backends.ibis.field_types import dtype

    for k, v in schema_data.items():
        if not isinstance(v, DataType):
            schema_data[k] = dtype(v)

    return schema_data


def updated_schema_data_for_mongodb(schema_data) -> t.Dict[str, DataType]:
    schema_data = {k: v for k, v in schema_data.items() if isinstance(v, DataType)}

    # MongoDB can store dict directly, so we don't need to serialize it.
    schema_data = {k: v for k, v in schema_data.items() if v.identifier != "json"}

    return schema_data


class JsonDataTypeFactory(DataTypeFactory):
    @staticmethod
    def check(data: t.Any) -> bool:
        try:
            json_serializer.encode_data(data)
            return True
        except Exception:
            return False

    @staticmethod
    def create(data: t.Any) -> DataType:
        return json_serializer
