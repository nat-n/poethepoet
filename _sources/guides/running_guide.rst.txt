Running tasks
=============

An example task
---------------

Poe tasks are defined in your **pyproject.toml** file under ``tool.poe.tasks``

The following toml example defines a task called `test` that consists of the associated command.

.. code-block:: toml

  [tool.poe.tasks]
  test = "pytest --cov=poethepoet"

This task can the be run via the poe cli as ``poe test``.

.. hint::

  If your pyproject defines pytest as a dependency with poetry, then poe will run the task with pytest from the poetry managed virtualenv, so you don't need to explicitly activate the virtualenv via ``poetry shell`` or ``poetry run``.


`Click here for a real example <https://github.com/nat-n/poethepoet/blob/main/pyproject.toml>`_.


Run a task with the poe CLI
---------------------------

The preferred way to run poe is via the standalone CLI.

.. code-block:: sh

  poe test

The above command can only be ran if you've :doc:`installed Poe globally<../installation>`, or if you've sourced the venv that Poe the Poet is installed in (e.g. using ``poetry shell``).


Running Poe as a Python module
---------------------------------------

You can also run poe as a python module

.. code-block:: sh

  python -m poethepoet [options] test [task_args]


Running Poe as a Poetry plugin
------------------------------
If you've installed it as a :doc:`poetry plugin<../poetry_plugin>` (for poetry >= 1.2), you can run it like so

.. code-block:: sh

  poetry self add poethepoet[poetry_plugin]
  poetry poe [options] test [task_args]


Running Poe as a Poetry dependency
----------------------------------
If you've installed it as a dev dependency with poetry, you can run it like so

.. code-block:: sh

  poetry add --group dev poethepoet
  poetry run poe [options] test [task_args]


.. hint::
  In this case you might want create an alias like :sh:`alias poe='poetry run poe'`.


Passing arguments
-----------------

By default additional arguments are passed to the task so

.. code-block:: sh

  poe test -v tests/favorite_test.py

will result in the following being run inside poetry's virtualenv

.. code-block:: sh

  pytest --cov=poethepoet -v tests/favorite_test.py

