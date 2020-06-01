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

By default poe doesn't set the current workind directory to run tasks, however the
parent directory of the toml file can be accessed as `$POE_ROOT` within the command
line and process.

Poe can also be configured to set the working directory to the project root for all
commands by including the following setting within the pyproject.toml.

.. code-block:: toml

  [tool.poe]
  run_in_project_root = true

Contributing
============

Sure, why not?

TODO
====

* make the cli more friendly with colors and supportive helpful messages
* support running tasks outside of poetry's virtualenv (or in another?)
* support "script" tasks defined as references to python functions
* test better
* task composition/aliases
* validate tool.poe config in toml
* maybe support declaring specific arguments for a task
* maybe try work well without poetry too

Licence
=======

MIT. Go nuts.
