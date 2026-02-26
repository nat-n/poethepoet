Global options
==============

The following options can be set for all tasks in a project directly under ``[tool.poe]``. These are called global options, in contrast with :doc:`task options<tasks/options>`.

**env** : ``dict[str, str]`` :ref:`📖<Global environment variables>`
  Define environment variables to be exposed to all tasks. These can be :ref:`extended on the task level<Setting task specific environment variables>`.

**envfile** : ``str`` | ``list[str]`` :ref:`📖<Global environment variables>`
  Link to one or more files defining environment variables to be exposed to all tasks.

**executor** : ``str`` | ``dict[str, str]`` :ref:`📖<Configure the executor for a task>`
  Specify the default executor type and/or configuration for all tasks in this project.

**include** : ``str`` | ``dict[str, str]`` | ``list[str | dict[str, str]]`` | :doc:`📖<../guides/include_guide>`
  Specify one or more other toml or json files to load tasks from.

**include_script** : ``str`` | ``dict[str, str]`` | ``list[str | dict[str, str]]`` :doc:`📖<../guides/packaged_tasks>`
  Load dynamically generated tasks from one or more python functions. This is similar to the :doc:`include global option<../guides/include_guide>`, except instead of providing paths to config files, one can reference python functions that generate task config, using the same syntax as for :doc:`script tasks<../tasks/task_types/script>`.

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
  When a task is declared as an array (instead of a table), then it is interpreted as the default array task type, which will be ``"sequence"`` unless otherwise specified. Valid options are ``"sequence"`` or ``"parallel"``.

**default_array_item_task_type** : ``"cmd" | "expr" | "ref" | "script" | "shell"``
  When a task is declared as a string inside an array (e.g. inline in a sequence task), then it is interpreted as the default array item task type, which will be ``"ref"`` unless otherwise specified.

Global environment variables
----------------------------

You can configure environment variables to be set for all poe tasks in the pyproject.toml file by specifying :toml:`tool.poe.env` like so

.. code-block:: toml

  [tool.poe.env]
  VAR1 = "FOO"
  VAR2 = "BAR BAR BLACK ${FARM_ANIMAL}"

The example above also demonstrates how – as with env vars defined at the task level – posix variable interpolation syntax may be used to define global env vars with reference to variables already defined in the host environment or in a referenced env file.

As with the task level option, you can indicated that a variable should only be set if not already set like so:

.. code-block:: toml

  [tool.poe.env]
  VAR1.default = "FOO"

Loading external environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also specify an env file (with bash-like syntax) to load for all tasks like so:

.. code-block:: bash
   :caption: .env

    STAGE=dev
    PASSWORD='!@#$%^&*('

.. code-block:: toml
   :caption: pyproject.toml

    [tool.poe]
    envfile = ".env"

The envfile global option also accepts a list of env files like so:

.. code-block:: toml

    [tool.poe]
    envfile = ["standard.env", "local.env"]

In this case the referenced files will be loaded in the given order.

.. important::

  The envfile option is also available with the same capabilities at :ref:`the task level<Loading environment variables from an env file>`.

Optional env files
""""""""""""""""""

Normally poe will emit a warning if a specified envfile is not found. If you consider an envfile to be optional, you can suppress these warnings by configuring the file path (or paths) under the ``optional`` prefix like so:

.. code-block:: toml

    [tool.poe]
    envfile.optional = ".env"

You can combine optional and expected envfiles like so:

.. code-block:: toml

    [tool.poe.envfile]
    expected = ["shared.env"]
    optional = ["local.env"]

In this example ``shared.env`` is considered mandatory, whereas ``local.env`` may be absent without generating noise. Using :toml:`envfile = ".env"` remains equivalent to setting :toml:`envfile.expected = ".env"` explicitly.

Resolving env file paths
""""""""""""""""""""""""

Normally envfile paths are resolved relative to the project root (that is the parent directory of the pyproject.toml). However when working with a monorepo it can also be useful to specify the path relative to the root of the git repository, which can be done by referencing the ``POE_GIT_DIR`` or ``POE_GIT_ROOT`` variables like so:

.. code-block:: toml

    [tool.poe]
    envfile = "${POE_GIT_DIR}/.env"

See the documentation on :ref:`Special variables<Special variables>` for a full explanation of how these variables work.

.. note::

  Environment variables loaded from env files have higher precedence than any inherited from the host environment, but lower precedence than env defined directly in the pyproject.toml file. Similarly ``optional`` env files are loaded after ``expected`` ones, so variables defined in ``optional`` files can override those defined in ``expected`` files.


Configure the executor
----------------------

You can configure poe to use a specific executor by setting
:toml:`tool.poe.executor`. Valid values include:

- **auto**: to automatically use the most appropriate of the following executors in order
- **poetry**: to run tasks in the poetry managed environment
- **uv**: to run tasks in an uv environment
- **virtualenv**: to run tasks in the indicated virtualenv (or else "./.venv" or "./venv" if present)
- **simple**: to run tasks without doing any specific environment setup

The default behavior is **auto**.

You specify a different executor to use as a global option, task level option, or at runtime with the ``--executor`` cli option.

For example you can make your whole project use the simple executor (no environment integration) by default like so:

.. code-block:: toml

    [tool.poe]
    executor = "simple"

Which is a short hand for the following table form which is required in order to pass options to the executor:

.. code-block:: toml

    [tool.poe.executor]
    type = "simple"

.. important::

  You can also configure the executor :ref:`at the task level<Configure the executor for a task>`, which will have higher precedence.
  Alternatively you can override the executor type at runtime by passing the ``--executor`` CLI option (before the task name) with the name of the executor to use, or the

Uv Executor
~~~~~~~~~~~

The uv executor can be configured with the following options, which translate into passing the corresponding CLI option to the `uv run command <https://docs.astral.sh/uv/reference/cli/#uv-run>`_:

**extra** : ``str`` | ``list[str]`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--extra>`__
  Include optional dependencies from the specified extra name.

**group** : ``str`` | ``list[str]`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--group>`__
  Include dependencies from the specified dependency group.

**no-group** : ``str`` | ``list[str]`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--no-group>`__
  Disable the specified dependency group.

**with** : ``str`` | ``list[str]`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--with>`__
  Run with the given packages installed.

**isolated** : ``bool`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--isolated>`__
  Run the command in a fresh emphemeral virtual environment, instead of the usual in-project .venv

**exact** : ``bool`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--exact>`__
  Sync the environment exactly, removing extraneous packages not in the requested groups (unlike the default inexact sync which only adds missing packages).

**no-sync** : ``bool`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--no-sync>`__
  Avoid syncing the virtual environment.

**locked** : ``bool`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--locked>`__
  Run without updating the uv.lock file.

**frozen** : ``bool`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--frozen>`__
  Run without updating the uv.lock file.

**no-project** : ``bool`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--no-project>`__
  Avoid discovering the project or workspace.

**python** : ``str`` `📖 <https://docs.astral.sh/uv/reference/cli/#uv-run--python>`__
  The Python interpreter to use for the run environment.

You can combine project and task level executor options and inheritance will work as you would expect:

.. code-block:: toml

  [tool.poe.executor]
  type = "uv"

  [tool.poe.tasks.test-py311]
  cmd = "pytest tests"
  executor = {isolated = true, python = "3.11", with = ["pytest"]}

  [tool.poe.tasks.test-py312]
  cmd = "pytest tests"
  executor = {isolated = true, python = "3.12", with = ["pytest"]}

This feature enables you to replace tools like tox by creating task variants for different Python versions or environments. See the :doc:`../guides/tox_replacement_guide` for a detailed guide on using poethepoet in this way.

This kind of task level executor config will even work seamlessly in projects that don't otherwise use `uv` if the executor type is specified at the task level.

Virtualenv Executor
~~~~~~~~~~~~~~~~~~~

The virtualenv executor can be configured with the following options:

**location** : ``bool``
  The path of the virtual environment to use. Defaults to ``./venv`` or ``./.venv``.

.. code-block:: toml

  [tool.poe.executor]
  type = "virtualenv"
  location = "myvenv"

If the virtualenv location is a relative path then it is resolved relative to the project root (the parent directory of the pyproject.toml file. However in a monorepo project it may also be defined relative to the git repo root by templating :ref:`these  special environment variables<Special variables>` like so:

.. code-block:: toml

  [tool.poe.executor]
  type = "virtualenv"
  location = "${POE_GIT_DIR}/myvenv"


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
