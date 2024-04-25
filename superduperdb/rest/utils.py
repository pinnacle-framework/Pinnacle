import re
import typing as t

from pinnacledb.base.document import Document


def _parse_query_part(part, documents, query, db: t.Optional[t.Any] = None):
    documents = [Document.decode(r, db=db) for r in documents]
    from pinnacledb.backends.mongodb.query import Collection

    part = part.replace(' ', '').replace('\n', '')
    part = part.replace('_documents', 'documents')
    part = part.split('.')
    for i, comp in enumerate(part):
        if i == 0:
            current = Collection(comp)
        else:
            match = re.match('^([a-zA-Z0-9_]+)\((.*)\)$', comp)
            if match is None:
                current = getattr(current, comp)
                continue
            if not match.groups()[1].strip():
                current = getattr(current, match.groups()[0])()
                continue

            comp = getattr(current, match.groups()[0])
            args_kwargs = [x.strip() for x in match.groups()[1].split(',')]
            args = []
            kwargs = {}
            for x in args_kwargs:
                if '=' in x:
                    k, v = x.split('=')
                    kwargs[k] = eval(v, {'documents': documents, 'query': query})
                else:
                    args.append(eval(x, {'documents': documents, 'query': query}))
            current = comp(*args, **kwargs)
    return current


def parse_query(query, documents, db: t.Optional[t.Any] = None):
    for i, q in enumerate(query):
        query[i] = _parse_query_part(q, documents, query[:i], db=db)
    return query[-1]


def strip_artifacts(r: t.Any):
    if isinstance(r, dict):
        if '_content' in r:
            return f'_artifact/{r["_content"]["file_id"]}', [r["_content"]["file_id"]]
        else:
            out = {}
            a_out = []
            for k, v in r.items():
                vv, tmp = strip_artifacts(v)
                a_out.extend(tmp)
                out[k] = vv
            return out, a_out
    elif isinstance(r, list):
        out = []
        a_out = []
        for x in r:
            xx, tmp = strip_artifacts(x)
            out.append(xx)
            a_out.extend(tmp)
        return out, a_out
    else:
        return r, []


if __name__ == '__main__':
    q = parse_query(
        [
            'documents.find($documents[0], a={"b": 1}).sort(c=1).limit(1)',
        ],
        [],
        [],
    )

    print(q)
