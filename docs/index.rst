.. toctree::
   :hidden:
   :maxdepth: 2

   installation
   poetry_plugin
   tasks/index
   configuration/index
   guides/index
   license

**************************
Poe the Poet Documentation
**************************

.. image:: https://img.shields.io/pypi/pyversions/poethepoet.svg
   :target: https://pypi.org/project/poethepoet/
   :alt: PyPI

.. image:: https://img.shields.io/pypi/v/poethepoet.svg
   :target: https://pypi.org/project/poethepoet/
   :alt: PyPI

.. image:: https://img.shields.io/pypi/dw/poethepoet
   :alt: PyPI - Downloads

.. image:: https://img.shields.io/pypi/l/ansicolortags.svg
   :alt: MIT

.. image:: https://img.shields.io/github/stars/nat-n/poethepoet?style=social
   :target: https://github.com/nat-n/poethepoet
   :alt: GitHub repo

Poe the Poet is a batteries included task runner that works well with |poetry_link|.

It provides a simple way to define project tasks within your pyproject.toml, and either a standalone CLI or a poetry plugin to run them using your project's virtual environment.

"Simple things should be simple, complex things should be possible." – Alan Kay


Top features
============

|V| Straight forward declaration of project tasks in your pyproject.toml

|V| Tasks are run in poetry's virtualenv (or another env you specify)

|V| Shell completion of task names (and global options too for zsh)

|V| The poe CLI can be used standalone, or as a plugin for the poetry

|V| Tasks can be commands, shell scripts, python expressions, or references to python functions

|V| Concise commands with extra arguments passed to the task :sh:`poe [options] task [task_args]`

|V| Easily define CLI arguments for your tasks

|V| Tasks can specify and reference environment variables, even without a shell

|V| Tasks are self documenting, with optional help messages (just run :sh:`poe` with no arguments)

|V| Tasks can be composed into sequences or DAGs

|V| Works with :code:`.env` files


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


Usage without poetry
====================

Poe the Poet was originally intended as the missing task runner for |poetry_link|. But it works just as well with any other kind of virtualenv, or simply as a general purpose way to define handy tasks for use within a certain directory structure! This behaviour is configurable via the :toml:`tool.poe.executor` global option.

By default poe will run tasks in the poetry managed virtual environment, if the pyproject.toml
contains a :toml:`tool.poetry` section. If it doesn't then poe looks for a virtualenv to
use at ``./.venv`` or ``./venv`` relative to the pyproject.toml.

If no virtualenv is found then poe will run tasks without any special environment management.


Run poe from anywhere
=====================

By default poe will detect when you're inside a project with a pyproject.toml in the root. However if you want to run it from elsewhere then that is supported by using the :sh:`--root` option to specify an alternate location for the toml file. The task will run with the given location as the current working directory.

In all cases the path to project root (where the pyproject.toml resides) will be available as :sh:`$POE_ROOT` within the command line and process.


.. |poetry_link| raw:: html

   <a href="https://python-poetry.org/" target="_blank">poetry</a>

.. |pipx_link| raw:: html

   <a href="https://pypa.github.io/pipx/" target="_blank">pipx</a>

