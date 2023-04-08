Global configuration
====================

Global environment variables
----------------------------

You can configure environment variables to be set for all poe tasks in the
pyproject.toml file by specifying :toml:`tool.poe.env` like so

.. code-block:: toml

  [tool.poe.env]
  VAR1 = "FOO"
  VAR2 = "BAR BAR BLACK ${FARM_ANIMAL}"

The example above also demonstrates how – as with env vars defined at the task level –
posix variable interpolation syntax may be used to define global env vars with reference
to variables already defined in the host environment or in a referenced env file.

As with the task level option, you can indicated that a variable should only be set if
not already set like so:

.. code-block:: toml

  [tool.poe.env]
  VAR1.default = "FOO"

You can also specify an env file (with bash-like syntax) to load for all tasks like so:

.. code-block:: bash

    # .env
    STAGE=dev
    PASSWORD='!@#$%^&*('

.. code-block:: toml

    [tool.poe]
    envfile = ".env"

The envfile global option also accepts a list of env files.

Default command verbosity
-------------------------

You can alter the verbosity level for poe commands by passing :bash:`--quiet` /
:bash:`-q` (which decreases verbosity) or :bash:`--verbose` / :bash:`-v` (which
increases verbosity) on the CLI.

If you want to change the default verbosity level for all commands, you can use
the :toml:`tool.poe.verbose` option in pyproject.toml like so:

.. code-block:: toml

  [tool.poe]
  verbosity = -1

:toml:`-1` is the quietest and :toml:`1` is the most verbose. :toml:`0` is the
default.

Note that the command line arguments are incremental: :bash:`-q` subtracts one
from the default verbosity, and :bash:`-v` adds one. So setting the default
verbosity to :toml:`-1` and passing :bash:`-v -v` on the command line is
equivalent to setting the verbosity to :toml:`0` and just passing :bash:`-v`.

Run poe from anywhere
---------------------

By default poe will detect when you're inside a project with a pyproject.toml in the
root. However if you want to run it from elsewhere then that is supported by using the
:bash:`--root` option to specify an alternate location for the toml file. The task will
run with the given location as the current working directory.

In all cases the path to project root (where the pyproject.toml resides) will be
available as :bash:`$POE_ROOT` within the command line and process.

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

You can configure poe to use a specific executor by setting
:toml:`tool.poe.executor.type`. Valid values include:

- **auto**: to automatically use the most appropriate of the following executors in order
- **poetry**: to run tasks in the poetry managed environment
- **virtualenv**: to run tasks in the indicated virtualenv (or else "./.venv" if present)
- **simple**: to run tasks without doing any specific environment setup

The default behaviour is auto.

For example the following configuration will cause poe to ignore the poetry environment
(if present), and instead use the virtualenv at the given location relative to the
parent directory.

.. code-block:: toml

  [tool.poe.executor]
  type = "virtualenv"
  location = "myvenv"

See below for more details.

Change the default shell interpreter
------------------------------------

Normally shell tasks are executed using a posix shell by default (see section for shell
tasks above). This default can be overridden to something else by setting the
*shell_interpreter* global option. In the following example we configure all shell tasks
to use *fish* by default.

.. code-block:: toml

  tool.poe.shell_interpreter = "fish"

  [tool.poe.tasks.fibonacci]
  help = "Output the fibonacci sequence up to 89"
  shell = """
    function fib --argument-names max n0 n1
      if test $max -ge $n0
        echo $n0
        fib $max $n1 (math $n0 + $n1)
      end
    end

    fib 89 1 1
  """
