import os
import sys

import sphinx_rtd_theme


sys.path.insert(0, os.path.abspath('..'))

extensions =[
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.mathjax',
    'sphinx.ext.ifconfig',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx.ext.napoleon',
    'sphinx_rtd_theme',
    'nbsphinx',
    'myst_parser',
]

autoclass_content = "both"

copyright = 'SuperDuperDB Inc., opensource@pinnacledb.com'

exclude_patterns = ['_build']

html_css_files = ['custom.css']
html_static_path = ['_static']
html_theme = 'sphinx_rtd_theme'

master_doc = 'index'

napoleon_google_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_numpy_docstring = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

nbsphinx_allow_errors = True

project = 'SuperDuperDB'
pygments_style = 'sphinx'

source_suffix = '.rst'
