Basic Usage
===========

Creating your first task
------------------------

When starting to use Poe, you will want to define your tasks in your :code:`pyproject.toml` file.

.. note::

  Poe is a plugin for Poetry. Poe tasks can be defined in the :code:`[tool.poe.tasks]` section of your :code:`pyproject.toml` file.

There exists a few different ways to define tasks. The simplest is to just define a command to run within the Poetry shell.

For instance, if you want to run your tests, you can define a task like so:

.. code-block:: toml

  [tool.poe.tasks]
  test = "pytest --cov=poethepoet"  # simple command based task

This will alias the command :code:`poe test` to :code:`pytest --cov=poethepoet`.

.. hint::

  Poe will run the command within the Poetry shell, so you don't need to activate the virtualenv.

There exists quite a few other types of tasks, such as shell tasks, python script tasks, and more.
You can find more information about them in the :ref:`Tasks` section.

.. code-block:: toml

  [tool.poe.tasks]
  test   = "pytest --cov=poethepoet"                                # simple command based task
  serve  = { script = "my_app.service:run(debug=True)" }            # python script based task
  tunnel = { shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &" }  # (posix) shell based task

Adding help text
----------------

You can add help text to your tasks by adding a :code:`help` key to your task definition, like so:

.. code-block:: toml

  [tool.poe.tasks.test]
  help = "Run the test suite"
  cmd = "pytest --cov=poethepoet"

  [tool.poe.tasks.serve]
  help = "Run the app in debug mode"
  script = "my_app.service:run(debug=True)"

  [tool.poe.tasks.tunnel]
  help = "Create an SSH tunnel to the production server"
  shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &"

This will allow you to run :code:`poe --help` and see the help text for your tasks.

.. code-block::

  $ poe --help
  Poe the Poet - A task runner that works well with poetry.
  version 0.19.0

  USAGE
    poe [-h] [-v | -q] [--root PATH] [--ansi | --no-ansi] task [task arguments]

  GLOBAL OPTIONS
    -h, --help     Show this help page and exit
    --version      Print the version and exit
    -v, --verbose  Increase command output (repeatable)
    -q, --quiet    Decrease command output (repeatable)
    -d, --dry-run  Print the task contents but don't actually run it
    --root PATH    Specify where to find the pyproject.toml
    --ansi         Force enable ANSI output
    --no-ansi      Force disable ANSI output

  CONFIGURED TASKS
    test           Run the test suite
    serve          Run the app in debug mode
    tunnel         Create an SSH tunnel to the production server

You can find a more complex example of tasks in `this repo's pyproject.toml <https://github.com/nat-n/poethepoet/blob/main/pyproject.toml#L43>`_ file.


Run a task with the :code:`poe` CLI
-----------------------------------

Once you have defined your tasks, you'll want to run them. Poe provides a CLI to run your tasks.

Using the above example of task definitions, you'd be able to run the following tasks:

.. code-block:: bash

  $ poe test
  $ poe serve
  $ poe tunnel

The above command can only be ran if you've installed Poe globally, or if you've sourced the venv that
Poe is installed in (e.g. using :code:`poetry shell`).

Running Poe as a Python module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also run it like so if you fancy

.. code-block:: bash

  python -m poethepoet [options] task [task_args]

Running Poe as a Poetry plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you've installed it as a poetry plugin (for poetry >= 1.2), you can run it like so

.. code-block:: bash

  poetry self add poethepoet[poetry_plugin]
  poetry poe [options] task_name [task_args]

Running Poe as a Poetry dependency
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you've installed it as a dev dependency with poetry, you can run it like so

.. code-block:: bash

  poetry add --group dev poethepoet
  poetry run poe [options] task_name [task_args]


.. hint::
  Though in that case you might like to alias it using :bash:`alias poe='poetry run poe'`.

Passing arguments
~~~~~~~~~~~~~~~~~

By default additional arguments are passed to the task so

.. code-block:: bash

  poe test -v tests/favorite_test.py

will result in the following being run inside poetry's virtualenv

.. code-block:: bash

  pytest --cov=poethepoet -v tests/favorite_test.py

