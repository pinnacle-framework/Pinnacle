import pytest
from pinnacle import CFG, pinnacle
from pinnacle.base.document import Document as D
from pinnacle.components.listener import Listener


@pytest.mark.skip
def test_end_2_end():
    memory_table = False
    if CFG.data_backend.endswith("csv"):
        memory_table = True
    _end_2_end(pinnacle(), memory_table=memory_table)


# TODO: Fix the test without torch
def _end_2_end(db, memory_table=False):
    import PIL.Image
    import torch.nn
    import torchvision
    from pinnacle.ext.torch.encoder import tensor
    from pinnacle.ext.torch.model import TorchModel

    fields = {
        "id": "str",
        "health": "int32",
        "age": "int32",
        "image": 'pinnacle_pillow.pil_image',
    }
    im = PIL.Image.open("test/material/data/test-image.jpeg")

    data_to_insert = [
        {"id": "1", "health": 0, "age": 25, "image": im},
        {"id": "2", "health": 1, "age": 26, "image": im},
        {"id": "3", "health": 0, "age": 27, "image": im},
        {"id": "4", "health": 1, "age": 28, "image": im},
    ]

    from pinnacle.components.table import Table

    t = Table(identifier="my_table", fields=fields)

    db.apply(t)
    t = db["my_table"]

    insert = t.insert(
        [
            D(
                {
                    "id": d["id"],
                    "health": d["health"],
                    "age": d["age"],
                    "image": d["image"],
                }
            )
            for d in data_to_insert
        ]
    )
    db.execute(insert)

    q = t.select("image", "age", "health")

    result = db.execute(q)
    for img in result:
        img = img.unpack()
        assert isinstance(img["image"], PIL.Image.Image)
        assert isinstance(img["age"], int)
        assert isinstance(img["health"], int)

    # preprocessing function
    preprocess = torchvision.transforms.Compose(
        [
            torchvision.transforms.Resize(256),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize(
                mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
            ),
        ]
    )

    def postprocess(x):
        return int(x.topk(1)[1].item())

    # create a torchvision model
    resnet = TorchModel(
        identifier="resnet18",
        preprocess=preprocess,
        postprocess=postprocess,
        object=torchvision.models.resnet18(pretrained=False),
        datatype='int32',
    )

    # Apply the torchvision model
    listener1 = Listener(
        model=resnet,
        key="image",
        select=t.select("id", "image"),
        predict_kwargs={"max_chunk_size": 3000},
        identifier="listener1",
    )
    db.apply(listener1)

    # also add a vectorizing model
    vectorize = TorchModel(
        preprocess=lambda x: torch.randn(32),
        object=torch.nn.Linear(32, 16),
        identifier="model_linear_a",
        datatype=tensor(dtype="float", shape=(16,)),
    )

    # create outputs query
    q = t.outputs(listener1.predict_id)

    # apply to the table
    listener2 = Listener(
        model=vectorize,
        key=listener1.outputs,
        select=q,
        predict_kwargs={"max_chunk_size": 3000},
        identifier="listener2",
    )
    db.apply(listener2)

    # Build query to get the results back
    q = t.outputs(listener2.outputs).select("id", "image", "age").filter(t.age > 25)

    # Get the results
    result = list(db.execute(q))
    assert result
    assert "image" in result[0].unpack()

    # TODO: Make this work

    q = t.select("id", "image", "age").filter(t.age > 25).outputs(listener2.outputs)

    # Get the results
    result = list(db.execute(q))
    assert listener2.outputs in result[0].unpack()
