************
Poe the Poet
************

A task runner that works well with poetry.

.. role:: bash(code)
   :language: bash
.. role:: fish(code)
   :language: fish
.. role:: zsh(code)
   :language: zsh
.. role:: toml(code)
   :language: toml
.. role:: python(code)
   :language: python

Features
========

✅  Straight forward declaration of project tasks in your pyproject.toml (kind of like npm scripts)

✅  Task are run in poetry's virtualenv by default

✅  Shell completion of task names (and global options too for zsh)

✅  Tasks can be commands (with or without a shell) or references to python functions (like tool.poetry.scripts)

✅  Short and sweet commands with extra arguments passed to the task :bash:`poe [options] task [task_args]`

✅  Tasks can specify and reference environment variables as if they were evaluated by a shell

✅  Tasks are self documenting, with optional help messages (just run poe without arguments)

✅  Tasks can be defined as a sequence of other tasks

✅  Works with .env files

✅  Can also be configured to execute tasks with any virtualenv or none (not just poetry)


Installation
============

Into your project (so it works inside poetry shell):

.. code-block:: bash

  poetry add --dev poethepoet

And into your default python environment (so it works outside of poetry shell)

.. code-block:: bash

  pip install poethepoet

Enable tab completion for your shell
------------------------------------

Poe comes with tab completion scripts for bash, zsh, and fish to save you keystrokes. How to install them will depend on your shell setup.

Zsh
~~~

.. code-block:: zsh

  # oh-my-zsh
  mkdir -p ~/.oh-my-zsh/completions
  poe _zsh_completion > ~/.oh-my-zsh/completions/_poe

  # without oh-my-zsh
  mkdir -p ~/.zfunc/
  poe _zsh_completion > ~/.zfunc/_poetry

Note that you'll need to start a new shell for the new completion script to be loaded. If it still doesn't work try adding a call to :bash:`compinit` to the end of your zshrc file.

Bash
~~~~

.. code-block:: bash

  # System bash
  poe _bash_completion > /etc/bash_completion.d/poe.bash-completion

  # Homebrew bash
  poe _bash_completion > $(brew --prefix)/etc/bash_completion.d/poe.bash-completion


How to ensure installed bash completions are enabled may vary depending on your system.

Fish
~~~~

.. code-block:: fish

  # Fish
  poe _fish_completion > ~/.config/fish/completions/poe.fish

  # Homebrew fish
  poe _fish_completion > (brew --prefix)/share/fish/vendor_completions.d/poe.fish


Basic Usage
===========

Define tasks in your pyproject.toml
-----------------------------------

`See a real example <https://github.com/nat-n/poethepoet/blob/master/pyproject.toml>`_

.. code-block:: toml

  [tool.poe.tasks]
  test       = "pytest --cov=poethepoet"                                # simple command based task
  mksandwich = { script = "my_package.sandwich:build" }                 # python script based task
  tunnel     = { shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &" }  # (posix) shell script based task

Run tasks with the poe cli
--------------------------

.. code-block:: bash

  poe test

Additional arguments are passed to the task so

.. code-block:: bash

  poe test -v tests/favorite_test.py

results in the following being run inside poetry's virtualenv

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
    greet = "echo Hello $USER"  # Environment variables work, even though there's no shell!

- **Script tasks** contain a reference to a python callable to import and execute, for
  example:

  .. code-block:: toml

    [tool.poe.tasks]
    fetch-assets = { "script" = "my_package.assets:fetch" }
    fetch-images = { "script" = "my_package.assets:fetch(only='images')" }

  As in the second example, is it possible to hard code literal arguments to the target
  callable.

  If extra arguments are passed to task on the command line, then they will be available
  to the called python function via :python:`sys.argv`.

- **Shell tasks** are similar to simple command tasks except that they are executed
  inside a new shell, and can consist of multiple separate commands, command
  substitution, pipes, background processes, etc.

  An example use case for this might be opening some ssh tunnels in the background with
  one task and closing them with another like so:

  .. code-block:: toml

    [tool.poe.tasks]
    pfwd = { "shell" = "ssh -N -L 0.0.0.0:8080:$STAGING:8080 $STAGING & ssh -N -L 0.0.0.0:5432:$STAGINGDB:5432 $STAGINGDB &" }
    pfwdstop = { "shell" = "kill $(pgrep -f "ssh -N -L .*:(8080|5432)")" }

- **Composite tasks** are defined as a sequence of other tasks as an array.

  By default the contents of the array are interpreted as references to other tasks (actually a ref task type), though this behaviour can be altered by setting the global :toml:`default_array_item_task_type` option to the name of another task type such as _cmd_, or by setting the :toml:`default_item_type` option locally on the sequence task.

  **An example task with references**

  .. code-block:: toml

    [tool.poe.tasks]

    test = "pytest --cov=src"
    build = "poetry build"
    _publish = "poetry publish"
    release = ["test", "build", "_publish"]

  Note that tasks with names prefixed with :code:`_` are not included in the documentation or directly executable, but can be useful for cases where a task is only needed for a sequence.

  **An example task with inline tasks expressed via inline tables**

  .. code-block:: toml

    release = [
      { cmd = "pytest --cov=src" },
      { script = "devtasks:build" },
      { ref = "_publish" },
    ]

  **An example task with inline script subtasks using default_item_type**

  .. code-block:: toml

    release.sequence = [
      "devtasks:run_tests(all=True)",
      "devtasks:build",
      "devtasks:publish",
    ]
    release.default_item_type = "script"

  A failure (non-zero result) will result in the rest of the tasks in the sequence not being executed, unless the :toml:`ignore_fail` option is set on the task like so:

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

Environment variables
---------------------

You can specify arbitrary environment variables to be set for a task by providing the env key like so:

  .. code-block:: toml

    [tool.poe.tasks]
    serve.script = "myapp:run"
    serve.env = { PORT = "9001" }

Notice this example uses deep keys which can be more convenient but aren't as well supported by some toml implementations.

The above example can be modified to only set the `PORT` variable if it is not already set by replacing the last line with the following:

  .. code-block:: toml

    serve.env.PORT.default "9001"


You can also specify an env file (with bashlike syntax) to load per task like so:

  .. code-block:: bash

    # .env
    STAGE=dev
    PASSWORD='!@#$%^&*('

  .. code-block:: toml

    [tool.poe.tasks]
    serve.script = "myapp:run"
    serve.envfile = ".env"

Declaring CLI options (experimental)
------------------------------------

By default extra CLI arguments are appended to the end of a cmd task, or exposed as
sys.argv in a script task. Alternatively it is possible to define CLI options that a
task should accept, which will be documented in the help for that task, and exposed to
the task in a way the makes the most sense for that task type.

Arguments for cmd and shell tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For cmd and shell tasks the values are exposed to the task as environment variables. For example given the following configuration:

.. code-block:: toml

  [tool.poe.tasks.passby]
  shell = """
  echo "hello $planet";
  echo "goodbye $planet";
  """
  help = "Pass by a planet!"
    [tool.poe.tasks.passby.args.planet] # the key of the arg is used as the name of the variable that the given value will be exposed as
    help = "Name of the planet to pass"
    default = "earth"
    required = false                    # by default all args are optional and default to ""
    options = ["-p", "--planet"]        # options are passed to ArgumentParser.add_argument as *args, if not given the the name value, i.e. [f"--{name}"]

the resulting task can be run like:

.. code-block:: bash

  poe passby --planet mars

Arguments for script tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~

Arguments can be defined for script tasks in the same way, but how they are exposed to
the underlying python function depends on how the script is defined.

In the following example, since not parenthesis are included for the referenced function,
all provided args will be passed to the function as kwargs:

.. code-block:: toml

  [tool.poe.tasks]
  build = { script = "project.util:build", args = ["dest", "version"]

Here the build method will be passed the two argument values (if provided) from the
command lines as kwargs.

Note that in this example, args are given as a list of strings. This abbreviated
form is equivalent to just providing a name for each argument and keeping the default
values for all other configuration (including empty string for the help message).

If there's a need to take control of how values are passed to the function, then this
is also possible as demonstrated in the following example:

.. code-block:: toml

  [tool.poe.tasks]
  build = { script = "project.util:build(dest, build_version=version)", args = ["dest", "version"]

Project-wide configuration options
==================================

Global environment variables
----------------------------

You can configure environment variables to be set for all poe tasks in the pyproject.toml file by specifying :toml:`tool.poe.env` like so

.. code-block:: toml

  [tool.poe.env]
  VAR1 = "FOO"
  VAR2 = "BAR"

As for the task level option, you can indicated that a variable should only be set if not already set like so:

.. code-block:: toml

  [tool.poe.env]
  VAR1.default = "FOO"

You can also specify an env file (with bashlike syntax) to load for all tasks like so:

  .. code-block:: bash

    # .env
    STAGE=dev
    PASSWORD='!@#$%^&*('

  .. code-block:: toml

    [tool.poe]
    envfile = ".env"

Default command verbosity
-------------------------

You can configure the verbosity level for poe commands by passing `--quiet` or
`--verbose` on the CLI. If you want to change the default verbosity level for
all commands, you can use the :toml:`tool.poe.verbose` option in pyproject.toml
like so:

.. code-block:: toml

  [tool.poe]
  verbosity = -1

:toml:`-1` is equivalent to :bash:`--quiet` and :toml:`1` is equivalent to
:bash:`--verbose`. :toml:`0` is the default.

Run poe from anywhere
---------------------

By default poe will detect when you're inside a project with a pyproject.toml in the
root. However if you want to run it from elsewhere that is supported too by using the
:bash:`--root` option to specify an alternate location for the toml file. The task will run
with the given location as the current working directory.

In all cases the path to project root (where the pyproject.toml resides) will be available
as :bash:`$POE_ROOT` within the command line and process.

Change the default task type
----------------------------

By default tasks defined as strings are interpreted as shell commands, and script tasks
require the more verbose table syntax to specify. For example:

.. code-block:: toml

  my_cmd_task = "cmd args"
  my_script_task = { "script" = "my_package.my_module:run" }

This behaviour can be reversed by setting the :toml:`default_task_type` option in your
pyproject.toml like so:

.. code-block:: toml

  [tool.poe]
  default_task_type = "script"

  [tool.poe.tasks]
  my_cmd_task = { "cmd" = "cmd args" }
  my_script_task = "my_package.my_module:run"


Change the executor type
------------------------

You can configure poe to use a specific executor by setting :toml:`tool.poe.executor.type`. Valid valued include:

  - auto: to automatically use the most appropriate of the following executors in order
  - poetry: to run tasks in the poetry managed environment
  - virtualenv: to run tasks in the indicated virtualenv (or else "./.venv" if present)
  - simple: to run tasks without doing any specific environment setup

For example the following configuration will cause poe to ignore the poetry environment (if present), and instead use the virtualenv at the given location relative to the parent directory.

.. code-block:: toml

  [tool.poe.executor]
  type = "virtualenv"
  location = "myvenv"


See below for more details.

Usage without poetry
====================

Poe the Poet was originally intended for use alongside poetry. But it works just as
well with any other kind of virtualenv, or standalone. This behaviour is configurable via the :toml:`tool.poe.executor` global option (see above).

By default poe will run tasks in the poetry managed environment, if the pyproject.toml contains a :toml:`tool.poetry` section. If it doesn't then poe looks for a virtualenv to use from :bash:`./.venv` or :bash:`./venv` relative to the pyproject.toml file. Otherwise it falls back to running tasks without any special environment management.

Contributing
============

There's plenty to do, come say hi in `the issues <https://github.com/nat-n/poethepoet/issues>`_! 👋

Also check out the `CONTRIBUTING.MD <https://github.com/nat-n/poethepoet/blob/main/.github/CONTRIBUTING.md>`_ 🤓


TODO
====

☐ support conditional execution (a bit like make targets) `#12 <https://github.com/nat-n/poethepoet/issues/12>`_

☐ support verbose mode for documentation that shows task definitions

☐ create documentation website `#11 <https://github.com/nat-n/poethepoet/issues/11>`_

☐ support third party task or executor types (e.g. pipenv) as plugins `#13 <https://github.com/nat-n/poethepoet/issues/13>`_

☐ provide poe as a poetry plugin `#14 <https://github.com/nat-n/poethepoet/issues/14>`_

☐ maybe support plumbum based tasks

Licence
=======

MIT.
