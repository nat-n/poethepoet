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

✅ Straight foward declaration of project tasks in your pyproject.toml (kind of like npm scripts)

✅ Task are run in poetry's virtualenv by default

✅ Tasks can be commands (with or without a shell) or references to python functions (like tool.poetry.scripts)

✅ Short and sweet commands with extra arguments passed to the task :bash:`poe [options] task [task_args]`

✅ Tasks can specify and reference environmental variables as if they were evaluated by a shell

✅ Tasks are self documenting, with optional help messages (just run poe without arguments)

✅ Tasks can be defined as a sequence of other tasks

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
  test       = "pytest --cov=poethepoet"                                # simple command based task
  mksandwich = { script = "my_package.sandwich:build" }                 # python script based task
  tunnel     = { shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &" }  # shell script based task

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

Types of task
=============

There are four types of task: simple commands (cmd), python scripts (script), shell
scripts (shell), and composite tasks (sequence).

- **Command tasks** contain a single command that will be executed without a shell.
  This covers most basic use cases for example:

  .. code-block:: toml

    [tool.poe.tasks]
    format = "black ."  # strings are interpreted as commands by default
    clean = """
    # Multiline commands including comments work too. Unescaped whitespace is ignored.
    rm -rf .coverage
           .mypy_cache
           .pytest_cache
           dist
           ./**/__pycache__
    """
    lint = { "cmd": "pylint poethepoet" }  # Inline tables with a cmd key work too
    greet = "echo Hello $USER"  # Environmental variables work, even though there's no shell!

- **Script tasks** contain a reference to a python callable to import and execute, for
  example:

  .. code-block:: toml

    [tool.poe.tasks]
    fetch-assets = { "script" = "my_package.assets:fetch" }
    fetch-images = { "script" = "my_package.assets:fetch(only='images')" }

  As in the second example, is it possible to hard code literal arguments to the target
  callable.

  If extra arguments are passed to task on the command line, then they will be available
  to the called python function via `sys.argv`.

- **Shell tasks** are similar to simple command tasks except that they are executed
  inside a new shell, and can consist of multiple seperate commands, command
  substitution, pipes, background processes, etc

  An example use case for this might be opening some ssh tunnels in the background with
  one task and closing them with another like so:

  .. code-block:: toml

    [tool.poe.tasks]
    pfwd = { "shell" = "ssh -N -L 0.0.0.0:8080:$STAGING:8080 $STAGING & ssh -N -L 0.0.0.0:5432:$STAGINGDB:5432 $STAGINGDB &" }
    pfwdstop = { "shell" = "kill $(pgrep -f "ssh -N -L .*:(8080|5432)")" }

- **Composite tasks** are defined as a sequence of other tasks as an array.

  By default the contents of the array as interpreted as references to other tasks (actually a ref task type), though this behavoir can be altered by setting the global `default_array_item_task_type` option to the name of another task type such as _cmd_.

  .. code-block:: toml

    [tool.poe.tasks]

    test = "pytest --cov=src"
    build = "poetry build"
    _publish = "poetry publish"
    release = ["test", "build", "_publish"]

  Note that tasks with names prefixed with `_` are not included in the documentation or directly executable, but can be useful for cases where a task is only needed for a sequence.

  A failure (non-zero result) will result in the rest of the tasks in the sequence not being executed, unless the `ignore_fail` option is set on the task like so:

  .. code-block:: toml

    [tool.poe.tasks]
    attempts.sequence = ["task1", "task2", "task3"]
    attempts.ignore_fail = true

Task level configuration
========================

Task help text
--------------

You can specifiy help text to be shown alongside the task name in the list of available tasks (such as when executing poe with no arguments), by adding a help key like so:

  .. code-block:: toml

    [tool.poe.tasks]
    style = {cmd = "black . --check --diff", help = "Check code style"}

Environmental variables
-----------------------

You can specify arbitrary environmental variables to be set for a task by providing the env key like so:

  .. code-block:: toml

    [tool.poe.tasks]
    serve.script = "myapp:run"
    serve.env = { PORT = 9001 }

Notice this exame uses deep keys which can be more convenient but aren't as well supported by some toml implementations.

Project-wide configuration options
==================================

Run poe from anywhere
---------------------

By default poe will detect when you're inside a project with a pyproject.toml in the
root. However if you want to run it from elsewhere that is supported too by using the
`--root` option to specify an alternate location for the toml file. The task will run
with with the given location as the current working directory.

In all cases the path to project root (where the pyproject.toml resides) is be available
as `$POE_ROOT` within the command line and process.

Change the default task type
----------------------------

By default tasks defined as strings are interpreted as shell commands, and script tasks
require the more verbose table syntax to specify. For example:

.. code-block:: toml

  my_cmd_task = "cmd args"
  my_script_task = { "script" = "my_package.my_module:run" }

This behavoir can be reversed by setting the `default_task_type` option in your
pyproject.toml like so:

.. code-block:: toml

  [tool.poe]
  default_task_type = "script"

  [tool.poe.tasks]
  my_cmd_task = { "cmd" = "cmd args" }
  my_script_task = "my_package.my_module:run"

Contributing
============

There's plenty to do, come say hi in the issues! 👋

TODO
====

☐ command line completion

☐ support declaring specific arguments for a task

☐ support conditional execution (a bit like make targets)

☐ support verbose mode for documentation that shows task definitions

☐ support running tasks outside of poetry's virtualenv (or in another?)

☐ try work well without poetry too

☐ maybe support plumbum based tasks

☐ maybe support third party task types as plugins

Licence
=======

MIT.
