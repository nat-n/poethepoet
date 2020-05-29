************
Poe the Poet
************

A task runner that works well with poetry.

Features
========

- Straight foward declaration of project tasks in your pyproject.toml (kind of like npm scripts)
- Task are run in poetry's virtualenv by default
- Short and sweet commands ``poe [options] task [task_args]``

Installation
============

.. code-block:: bash

  pip install poethepoet

Usage
=====

Define tasks in your pyproject.toml
-----------------------------------

`See a real example <https://github.com/nat-n/poethepoet/blob/master/pyproject.toml>`_

.. code-block:: toml

  [tool.poe.tasks]
  test = pytest --cov=poethepoet

Run tasks with the poe cli
--------------------------

.. code-block:: bash

  poe test

Additional argument are passed to the task so

.. code-block:: bash

  poe test -v tests/favorite_test.py

results in

.. code-block:: bash

  pytest --cov=poethepoet -v tests/favorite_test.py

You can also run it like so if you fancy

.. code-block:: bash

  python -m poethepoet

Contributing
============

Please do.

TODO
====

* make the cli more friendly with colors and supportive helpful messages
* support running tasks outside of poetry's virtualenv (or in another?)
* the abiltiy to declare specific arguments for a task
* test better
* task aliases
* more nuanced awareness of virtualenv

Licence
=======

MIT. Go nuts.
