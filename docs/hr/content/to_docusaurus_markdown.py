import json
import os
import re
import sys


CODE_BLOCK = ['```python\n', '\n        ```']
PREAMBLE = """import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

"""
TABS_WRAPPER = """
<Tabs>
{body}
</Tabs>
"""
  
TABS_ITEM = """    <TabItem value="{title}" label="{title}" default>
        {content}
    </TabItem>"""


def render_chunks_as_md(chunks):
    output = ''
    for chunk in chunks:
        if 'content' in chunk:
            output += ''.join(chunk['content'])
        elif 'tabs' in chunk:
            tabs = []
            for tab in chunk['tabs']:
                tab = TABS_ITEM.format(
                    content='        '.join(tab['content']),
                    title=tab['title']
                )
                tabs.append(tab)
            output += TABS_WRAPPER.format(body='\n'.join(tabs))
    return PREAMBLE + output


def render_notebook_as_chunks(nb):
    chunks = []
    for cell in nb['cells']:
        if cell['cell_type'] == 'markdown':
            chunks.append({
                'content': cell['source'] + ['\n', '\n']
            })

        elif cell['cell_type'] == 'code':
            if not cell['source']:
                continue

            match = re.match('^#[ ]+<([a-z]+):([^\>]+)>', cell['source'][0])

            if match and match.groups()[0] == 'tab':
                title = match.groups()[1].strip()
                if 'tabs' not in chunks[-1]:
                    chunks.append({'tabs': []})
                chunks[-1]['tabs'].append({
                    'content': [CODE_BLOCK[0], *cell['source'][1:], CODE_BLOCK[-1]],
                    'title': title,
                })
            elif match:  # testing not handled yet
                continue
            else:
                chunks.append({
                    'content': [CODE_BLOCK[0], *cell['source'], CODE_BLOCK[-1].replace(' ', '') + '\n\n']
                }
            )
        else:
            raise Exception(f'Unknown source type {cell["cell_type"]}, {cell}')

    return chunks



if __name__ == '__main__':
    directory = sys.argv[1]

    FILES = os.listdir(directory)

    for file in FILES:
        if file.startswith('_'):
            continue
        if not file.endswith('.ipynb'):
            continue
        with open(f'{directory}/{file}') as f:
            content = json.load(f)
        print(file)
        head = content['cells'][0]['source'][0].strip()
        if head == '<!-- TABS -->':
            title = content['cells'][0]['source'][1].strip().replace('# ', '')
            print(f'processing {file} with tabs...')
            chunks = render_notebook_as_chunks(content)
            md = render_chunks_as_md(chunks)

            md = f'---\nsidebar_label: {title}\n---\n' + md

            file = file.split('.')[0]
            target = '_'.join(title.lower().strip().split())
            assert file == target, f'{file} != {target}'
            with open(f'{directory}/{file}.md', 'w') as f:
                f.write(md)
        else:
            print(f'processing {directory}/{file} with Jupyter convert...')
            os.system(f'jupyter-nbconvert --clear-output {directory}/{file}')
            os.system(f'jupyter-nbconvert --to=markdown {directory}/{file}')