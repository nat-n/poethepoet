# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Poe The Poet'
copyright = 'MIT License'
author = 'Nat Noordanus <n@natn.me>'
release = '0.19.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autosectionlabel",  # Automatically add section labels, which can be used as :ref:`My section title`
    "sphinx.ext.githubpages"
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
rst_prolog = """
.. role:: sh(code)
   :language: sh
.. role:: bash(code)
   :language: bash
.. role:: fish(code)
   :language: fish
.. role:: zsh(code)
   :language: zsh
.. role:: toml(code)
   :language: toml
.. role:: python(code)
   :language: python
.. |V| unicode:: ✅ 0xA0 0xA0
   :trim:

"""


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
html_title = "Poe the Poet"
html_favicon = '_static/favicon.ico'
html_theme_options = {
    "light_logo": "poe_logo_x2000.png",
    "dark_logo": "poe_logo_x2000.png",
}