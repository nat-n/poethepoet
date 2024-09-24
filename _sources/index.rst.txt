.. toctree::
   :hidden:
   :maxdepth: 2

   installation
   poetry_plugin
   global_options
   tasks/index
   guides/index
   env_vars
   license

**************************
Poe the Poet Documentation
**************************

.. image:: https://img.shields.io/github/stars/nat-n/poethepoet?style=social
   :target: https://github.com/nat-n/poethepoet
   :alt: GitHub repo

.. image:: https://img.shields.io/pypi/pyversions/poethepoet.svg
   :target: https://pypi.org/project/poethepoet/
   :alt: PyPI

.. image:: https://img.shields.io/pypi/v/poethepoet.svg
   :target: https://pypi.org/project/poethepoet/
   :alt: PyPI

.. image:: https://img.shields.io/pypi/dm/poethepoet
   :target: https://pypistats.org/packages/poethepoet
   :alt: PyPI - Downloads

.. image:: https://img.shields.io/pypi/l/ansicolortags.svg
   :target: https://github.com/nat-n/poethepoet/blob/main/LICENSE
   :alt: MIT

Poe the Poet is a batteries included task runner that works well with |poetry_link|.

It provides a simple way to define project tasks within your pyproject.toml, and either a standalone CLI or a poetry plugin to run them using your project's virtual environment.

"Simple things should be simple, complex things should be possible." – Alan Kay


Top features
============

|V| Straight forward declaration of project tasks in your pyproject.toml (or :doc:`poe_tasks.toml<./guides/without_poetry>`)

|V| Tasks are run in poetry's virtualenv (or another env you specify)

|V| :ref:`Shell completion of task names<shell_completion>` (and global options too for zsh)

|V| The poe CLI can be used standalone, or as a :doc:`plugin for poetry<./poetry_plugin>`

|V| Tasks can be :doc:`commands<./tasks/task_types/cmd>`, :doc:`shell scripts<./tasks/task_types/shell>`, :doc:`python expressions<./tasks/task_types/expr>`, or references to :doc:`python functions<./tasks/task_types/script>`

|V| Concise commands with extra arguments passed to the task :sh:`poe [options] task [task_args]`

|V| Easily :doc:`define CLI arguments<./guides/args_guide>` for your tasks

|V| Tasks can specify and :ref:`reference environment variables<ref_env_vars>`, even without a shell

|V| Tasks are :doc:`self documenting<./guides/help_guide>`, with optional help messages (just run :sh:`poe` with no arguments)

|V| Tasks can be composed into :ref:`sequences<sequence_composition>` or :ref:`DAGs<graph_composition>`

|V| Works with :ref:`.env files<envfile_option>`

|V| Can be :doc:`used as a library<./guides/library_guide>` to embed in other tools

|V| Also works fine :doc:`without poetry<./guides/without_poetry>`


Quick start
===========

1.
  Install the CLI *globally* from PyPI using |pipx_link| (or via :doc:`another method <installation>`):

  .. code-block:: sh

    pipx install poethepoet

2.
  Add a section for poe tasks to your pyproject.toml

  .. code-block:: toml

   [tool.poe.tasks]
   test         = "pytest --cov=my_app"                         # a simple command task
   serve.script = "my_app.service:run(debug=True)"              # python script based task
   tunnel.shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &"   # (posix) shell based task

  `Click here for a real example <https://github.com/nat-n/poethepoet/blob/main/pyproject.toml>`_.

3.
  Run one of your tasks using the CLI

  .. code-block:: sh

    poe test -v

  The extra argument is appended to the task command.

.. hint::

  If you're using |poetry_link|, then poe will automatically use the poetry managed virtualenv to find executables and python libraries, without needing to use ``poetry run`` or ``poetry shell``.


Run poe from anywhere
=====================

By default poe will detect when you're inside a project with a pyproject.toml in the root. However if you want to run it from elsewhere then that is supported by using the :sh:`-C` option to specify an alternate location for the toml file. The task will run with the given location as the current working directory.

In all cases the path to project root (where the pyproject.toml resides) will be available as :sh:`$POE_ROOT` within the command line and process. The variable :sh:`$POE_PWD` contains the original working directory from which poe was run.

Using this feature you can also define :doc:`global tasks<./guides/global_tasks>` that are not associated with any particular project.


.. |pipx_link| raw:: html

   <a href="https://pypa.github.io/pipx/" target="_blank">pipx</a>

.. |poetry_link| raw:: html

   <a href="https://python-poetry.org/" target="_blank">poetry</a>
