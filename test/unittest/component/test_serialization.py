from pinnacle.components.datatype import dill_serializer
from pinnacle.components.model import ObjectModel


def test_model():
    m = ObjectModel(
        identifier='test',
        datatype=dill_serializer,
        object=lambda x: x + 1,
    )
    m_dict = m.dict()
    assert m_dict['identifier'] == m.identifier
    assert m_dict['object'].bytes == dill_serializer._encode_data(m.object)
    assert m_dict['datatype'].identifier == 'dill_serializer'
