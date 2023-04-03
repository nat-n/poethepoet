**************************
Poe the Poet Documentation
**************************

.. image:: https://img.shields.io/pypi/v/poethepoet.svg
   :target: https://pypi.org/project/poethepoet/
   :alt: PyPI

**Poe the Poet** is a task runner that works well with poetry.

Features
========

|V| Straight forward declaration of project tasks in your pyproject.toml (kind of like npm scripts)

|V| Tasks are run in poetry's virtualenv (or another env you specify)

|V| Shell completion of task names (and global options too for zsh)

|V| Can be used standalone or as a poetry plugin

|V| Tasks can be commands, shell scripts, or references to python functions (like :code:`tool.poetry.scripts`)

|V| Short and sweet commands with extra arguments passed to the task :bash:`poe [options] task [task_args]`, or you can define arguments explicitly.

|V| Tasks can specify and reference environment variables as if they were evaluated by a shell

|V| Tasks are self documenting, with optional help messages (just run `poe` without arguments)

|V| Tasks can be composed into sequences or DAGs

|V| Works with :code:`.env` files

Learn more
==========

.. toctree::
   :maxdepth: 2

   introduction/index
   tasks/index
   configuration/index
   guides/index
   contributing
