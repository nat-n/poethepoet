.. Poe The Poet documentation master file, created by
   sphinx-quickstart on Fri Mar 31 14:48:14 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

********
Welcome!
********

.. image:: https://img.shields.io/pypi/v/poethepoet.svg
   :target: https://pypi.python.org/pypi/poethepoet
   :alt: PyPI

**Poe The Poet** is a task runner that works well with poetry.

Features
========

|V| Straight forward declaration of project tasks in your pyproject.toml (kind of like npm scripts)

|V| Task are run in poetry's virtualenv (or another env you specify)

|V| Shell completion of task names (and global options too for zsh)

|V| Can be used standalone or as a poetry plugin

|V| Tasks can be commands (with or without a shell) or references to python functions (like :code:`tool.poetry.scripts`)

|V| Short and sweet commands with extra arguments passed to the task :bash:`poe [options] task [task_args]`, or you can define arguments explicitly.

|V| Tasks can specify and reference environment variables as if they were evaluated by a shell

|V| Tasks are self documenting, with optional help messages (just run poe without arguments)

|V| Tasks can be defined as a sequence of other tasks

|V| Works with :code:`.env` files

Documentation
=============

.. toctree::
   :maxdepth: 2

   getting_started/index
   tutorials/index
   tasks/index
   configuration/index
   contributing
