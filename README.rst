************
Poe the Poet
************

A task runner that works well with poetry.

.. role:: bash(code)
   :language: bash

.. role:: toml(code)
   :language: toml

Features
========

- Straight foward declaration of project tasks in your pyproject.toml (kind of like npm
  scripts)
- Task are run in poetry's virtualenv by default
- Short and sweet commands with extra arguments passed to the task
  :bash:`poe [options] task [task_args]`
- tasks can reference environmental variables as if they were evaluated by a shell

Installation
============

Into your project (so it works inside poetry shell):

.. code-block:: bash

  poetry add --dev poethepoet

And into your default python environment (so it works outside of poetry shell)

.. code-block:: bash

  pip install poethepoet

Basic Usage
===========

Define tasks in your pyproject.toml
-----------------------------------

`See a real example <https://github.com/nat-n/poethepoet/blob/master/pyproject.toml>`_

.. code-block:: toml

  [tool.poe.tasks]
  test = "pytest --cov=poethepoet"

Run tasks with the poe cli
--------------------------

.. code-block:: bash

  poe test

Additional argument are passed to the task so

.. code-block:: bash

  poe test -v tests/favorite_test.py

results in the following be run inside poetry's virtualenv

.. code-block:: bash

  pytest --cov=poethepoet -v tests/favorite_test.py

You can also run it like so if you fancy

.. code-block:: bash

  python -m poethepoet [options] task [task_args]

Or install it as a dev dependency with poetry and run it like

.. code-block:: bash

  poetry add --dev poethepoet
  poetry run poe [options] task [task_args]

Though it that case you might like to do :bash:`alias poe='poetry run poe'`.

Advanced usage
==============

Run poe from anywhere
---------------------

By default poe will detect when you're inside a project with a pyproject.toml in the
root. However if you want to run it from elsewhere that is supported too by using the
`--root` option to specify an alternate location for the toml file.

By default poe will set the working directory to run tasks. If you want tasks to inherit
the working directory from the environment that you disable this by setting the
following in your pyproject.toml.

.. code-block:: toml

  [tool.poe]
  run_in_project_root = false

In all cases the path to project root (where the pyproject.toml resides) is be available
as `$POE_ROOT` within the command line and process.

Contributing
============

Sure, why not?

TODO
====

* support running tasks outside of poetry's virtualenv (or in another?)
* support "script" tasks defined as references to python functions
* test better
* task composition/aliases
* maybe support declaring specific arguments for a task
* maybe try work well without poetry too

Licence
=======

MIT. Go nuts.
