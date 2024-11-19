import os

from pinnacle import CFG, Template, pinnacle

skips = []


def test_template():
    CFG.auto_schema = True

    db = pinnacle()

    template_name = os.environ['pinnacle_TEMPLATE']

    if template_name in skips:
        print(f'Skipping template {template_name}')
        return

    t = Template.read(f'templates/{template_name}')

    db.apply(t)

    assert f'sample_{template_name}' in db.show('table')

    sample = db[f'sample_{template_name}'].select().limit(2).tolist()

    assert sample

    print('Got sample:', sample)
    print(f'Got {len(sample)} samples')

    app = t()

    db.apply(app)
