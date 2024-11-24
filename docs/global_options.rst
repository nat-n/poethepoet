Global options
==============

The following options can be set for all tasks in a project directly under ``[tool.poe]``. These are called global options, in contrast with :doc:`task options<tasks/options>`.


**env** : ``dict[str, str]`` :ref:`📖<Global environment variables>`
  Define environment variables to be exposed to all tasks. These can be :ref:`extended on the task level<Setting task specific environment variables>`.

**envfile** : ``str`` | ``list[str]`` :ref:`📖<Global environment variables>`
  Link to one or more files defining environment variables to be exposed to all tasks.

**executor** : ``dict[str, str]`` :ref:`📖<Change the executor type>`
  Override the default behavior for selecting an executor for tasks in this project.

**include** : ``str`` | ``list[str]`` | ``dict[str, str]`` :doc:`📖<../guides/include_guide>`
  Specify one or more other toml or json files to load tasks from.

**shell_interpreter** : ``str`` | ``list[str]`` :ref:`📖<Change the default shell interpreter>`
  Change the default interpreter to use for executing :doc:`shell tasks<../tasks/task_types/shell>`.

**poetry_command** : ``str`` :ref:`📖<Configuring the plugin>`
  Change the name of the task poe registers with poetry when used as a plugin.

**poetry_hooks** : ``dict[str, str]`` :ref:`📖<Hooking into poetry commands>`
  Register tasks to run automatically before or after other poetry CLI commands.

**verbosity** : ``int``
  Set the default verbosity level for tasks in this project. The default value is ``0``, providing the ``-v`` global CLI option increases it by ``1``, whereas the ``-q`` global CLI option decreases it by ``1``.

**default_task_type** : ``"cmd" | "expr" | "ref" | "script" | "shell"``
  When a task is declared as a string (instead of a table), then it is interpreted as the default task type, which will be ``"cmd"`` unless otherwise specified.

**default_array_task_type** : ``str``
  When a task is declared as an array (instead of a table), then it is interpreted as the default array task type, which will be ``"sequence"`` unless otherwise specified. Currently the sequence task type is the only one that can be defined as an array.

**default_array_item_task_type** : ``"cmd" | "expr" | "ref" | "script" | "shell"``
  When a task is declared as a string inside an array (e.g. inline in a sequence task), then it is interpreted as the default array item task type, which will be ``"ref"`` unless otherwise specified.

Global environment variables
----------------------------

You can configure environment variables to be set for all poe tasks in the pyproject.toml file by specifying :toml:`tool.poe.env` like so

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
   :caption: .env

    STAGE=dev
    PASSWORD='!@#$%^&*('

.. code-block:: toml
   :caption: pyproject.toml

    [tool.poe]
    envfile = ".env"

The envfile global option also accepts a list of env files like so.

.. code-block:: toml

    [tool.poe]
    envfile = ["standard.env", "local.env"]

In this case the referenced files will be loaded in the given order.

Normally envfile paths are resolved relative to the project root (that is the parent directory of the pyproject.toml). However when working with a monorepo it can also be useful to specify the path relative to the root of the git repository, which can be done by referenceing the ``POE_GIT_DIR`` or ``POE_GIT_ROOT`` variables like so:

.. code-block:: toml

    [tool.poe]
    envfile = "${POE_GIT_DIR}/.env"

See the documentation on :ref:`Special variables<Special variables>` for a full explanation of how these variables work.

Change the executor type
------------------------

You can configure poe to use a specific executor by setting
:toml:`tool.poe.executor.type`. Valid values include:

- **auto**: to automatically use the most appropriate of the following executors in order
- **poetry**: to run tasks in the poetry managed environment
- **virtualenv**: to run tasks in the indicated virtualenv (or else "./.venv" or "./venv" if present)
- **simple**: to run tasks without doing any specific environment setup

The default behaviour is **auto**.

For example, the following configuration will cause poe to ignore the poetry environment
(if present), and instead use the virtualenv at the given location relative to the
parent directory. If no location is specified for a virtualenv then the default behavior is to use the virtualenv from ``./venv`` or ``./.venv`` if available.

.. code-block:: toml

  [tool.poe.executor]
  type = "virtualenv"
  location = "myvenv"

.. important::

  This global option can be overridden at runtime by providing the ``--executor`` cli option before the task name with the name of the executor type to use.

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

Run poe from anywhere
---------------------

By default poe will detect when you're inside a project with a pyproject.toml in the
root. However if you want to run it from elsewhere then that is supported by using the
:bash:`-C` option to specify an alternate location for the toml file. The task will
run with the given location as the current working directory.

In all cases the path to project root (where the pyproject.toml resides) will be
available as :bash:`$POE_ROOT` within the command line and process.
