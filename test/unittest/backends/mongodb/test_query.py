from pinnacledb.backends.mongodb import query as q
from pinnacledb.base.document import Document


def test_select_missing_outputs(local_db):
    docs = list(local_db.execute(q.Collection('documents').find({}, {'_id': 1})))
    ids = [r['_id'] for r in docs[: len(docs) // 2]]
    local_db.execute(
        q.Collection('documents').update_many(
            {'_id': {'$in': ids}},
            Document({'$set': {'_outputs.x.test_model_output': 'test'}}),
        )
    )

    select = q.Collection('documents').find({}, {'_id': 1})
    modified_select = select.select_ids_of_missing_outputs('x', 'test_model_output')

    out = list(local_db.execute(modified_select))
    assert len(out) == (len(docs) - len(ids))
