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
.. |•| unicode:: ✅ 0xA0 0xA0
   :trim:

Features
========

|•| Straight forward declaration of project tasks in your pyproject.toml (kind of like npm scripts)

|•| Task are run in poetry's virtualenv (or another env you specify)

|•| Shell completion of task names (and global options too for zsh)

|•| Tasks can be commands (with or without a shell) or references to python functions (like tool.poetry.scripts)

|•| Short and sweet commands with extra arguments passed to the task :bash:`poe [options] task [task_args]`

|•| Tasks can specify and reference environment variables as if they were evaluated by a shell

|•| Tasks are self documenting, with optional help messages (just run poe without arguments)

|•| Tasks can be defined as a sequence of other tasks

|•| Works with .env files


Installation
============

Into your project (so it works inside poetry shell):

.. code-block:: bash

  poetry add --dev poethepoet

And into any python environment (so it works outside of poetry shell)

.. code-block:: bash

  pip install poethepoet

Enable tab completion for your shell
------------------------------------

Poe comes with tab completion scripts for bash, zsh, and fish to save you keystrokes.
How to install them will depend on your shell setup.

Zsh
~~~

.. code-block:: zsh

  # oh-my-zsh
  mkdir -p ~/.oh-my-zsh/completions
  poe _zsh_completion > ~/.oh-my-zsh/completions/_poe

  # without oh-my-zsh
  mkdir -p ~/.zfunc/
  poe _zsh_completion > ~/.zfunc/_poetry

Note that you'll need to start a new shell for the new completion script to be loaded.
If it still doesn't work try adding a call to :bash:`compinit` to the end of your zshrc
file.

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
  test   = "pytest --cov=poethepoet"                                # simple command based task
  serve  = { script = "my_app.service:run(debug=True)" }            # python script based task
  tunnel = { shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &" }  # (posix) shell based task

Run tasks with the poe cli
--------------------------

.. code-block:: bash

  poe test

By default additional arguments are passed to the task so

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

There are four types of task: simple commands *(cmd)*, python scripts *(script)*, shell
scripts *(shell)*, and sequence tasks *(sequence)*.

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
    fetch-images = { "script" = "my_package.assets:fetch(only='images', log=environ['LOG_PATH'])" }

  As in the second example, is it possible to hard code literal arguments to the target
  callable. In fact a subset of python syntax, operators, and globals can be used inline
  to define the arguments to the function using normal python syntax, including environ
  (from the os package) to access environment variables that are available to the task.

  If extra arguments are passed to task on the command line (and no CLI args are
  declared), then they will be available within the called python function via
  :python:`sys.argv`.

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

  By default the contents of the array are interpreted as references to other tasks
  (actually a ref task type), though this behaviour can be altered by setting the global
  :toml:`default_array_item_task_type` option to the name of another task type such as
  *cmd*, or by setting the :toml:`default_item_type` option locally on the sequence task.

  **An example task with references**

  .. code-block:: toml

    [tool.poe.tasks]

    test = "pytest --cov=src"
    build = "poetry build"
    _publish = "poetry publish"
    release = ["test", "build", "_publish"]

  Note that tasks with names prefixed with :code:`_` are not included in the
  documentation or directly executable, but can be useful for cases where a task is only
  needed for referencing from another task.

  **An example task with inline tasks expressed via inline tables**

  .. code-block:: toml

    release = [
      { cmd = "pytest --cov=src" },
      { script = "devtasks:build" },
      { ref = "_publish" },
    ]

  **An example task with inline tasks expressed via an array of tables**

  .. code-block:: toml

    [tool.poe.tasks]

      [[tool.poe.tasks.release]]
      cmd = "pytest --cov=src"

      [[tool.poe.tasks.release]]
      script = "devtasks:build"

      [[tool.poe.tasks.release]]
      ref = "_publish"

  **An example task with inline script subtasks using default_item_type**

  .. code-block:: toml

    release.sequence = [
      "devtasks:run_tests(all=True)",
      "devtasks:build",
      "devtasks:publish",
    ]
    release.default_item_type = "script"

  A failure (non-zero result) will result in the rest of the tasks in the sequence not
  being executed, unless the :toml:`ignore_fail` option is set on the task to
  :toml:`true` or :toml:`"return_zero"` like so:

  .. code-block:: toml

    [tool.poe.tasks]
    attempts.sequence = ["task1", "task2", "task3"]
    attempts.ignore_fail = "return_zero"

  If you want to run all the subtasks in the sequence but return non-zero result in the
  end of the sequence if any of the subtasks have failed you can set :toml:`ignore_fail`
  option to the :toml:`return_non_zero` value like so:

  .. code-block:: toml

    [tool.poe.tasks]
    attempts.sequence = ["task1", "task2", "task3"]
    attempts.ignore_fail = "return_non_zero"

Task level configuration
========================

Task help text
--------------

You can specify help text to be shown alongside the task name in the list of available
tasks (such as when executing poe with no arguments), by adding a help key like so:

.. code-block:: toml

    [tool.poe.tasks]
    style = {cmd = "black . --check --diff", help = "Check code style"}

Environment variables
---------------------

You can specify arbitrary environment variables to be set for a task by providing the
env key like so:

.. code-block:: toml

    [tool.poe.tasks]
    serve.script = "myapp:run"
    serve.env = { PORT = "9001" }

Notice this example uses deep keys which can be more convenient but aren't as well
supported by some toml implementations.

The above example can be modified to only set the `PORT` variable if it is not already
set by replacing the last line with the following:

.. code-block:: toml

    serve.env.PORT.default = "9001"


You can also specify an env file (with bash-like syntax) to load per task like so:

.. code-block:: bash

    # .env
    STAGE=dev
    PASSWORD='!@#$%^&*('

.. code-block:: toml

    [tool.poe.tasks]
    serve.script  = "myapp:run"
    serve.envfile = ".env"

Declaring CLI arguments
-----------------------

By default extra arguments passed to the poe CLI following the task name are appended to
the end of a cmd task, or exposed as sys.argv in a script task (but will cause an error
for shell or sequence tasks). Alternatively it is possible to define named arguments
that a task should accept, which will be documented in the help for that task, and
exposed to the task in a way the makes the most sense for that task type.

In general named arguments can take one of the following three forms:

- **positional arguments** which are provided directly following the name of the task like
   :bash:`poe task-name arg-value`

- **option arguments** which are provided like
   :bash:`poe task-name --option-name arg-value`

- **flags** which are either provided or not, but don't accept a value like
   :bash:`poe task-name --flag`

The value for the named argument is then accessible by name within the task content,
though exactly how will depend on the type of the task as detailed below.


Configuration syntax
~~~~~~~~~~~~~~~~~~~~

Named arguments are configured by declaring the *args* task option as either an array or
a subtable.


Array configuration syntax
""""""""""""""""""""""""""

The array form may contain string items which are interpreted as an option argument with
the given name.

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "myapp:run"
    args = ["host", "port"]

This example can be invoked as

.. code-block:: bash

    poe serve --host 0.0.0.0 --port 8001

Items in the array can also be inline tables to allow for more configuration to be
provided to the task like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "myapp:run"
    args = [{ name = "host", default = "localhost" }, { name = "port", default = "9000" }]

You can also use the toml syntax for an array of tables like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "myapp:run"
    help = "Run the application server"

      [[tool.poe.tasks.serve.args]]
      name = "host"
      options = ["-h", "--host"]
      help = "The host on which to expose the service"
      default = "localhost"

      [[tool.poe.tasks.serve.args]]
      name = "port"
      options = ["-p", "--port"]
      help = "The port on which to expose the service"
      default = "8000"


Table configuration syntax
""""""""""""""""""""""""""

You can also use the toml syntax for subtables like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "myapp:run"
    help = "Run the application server"

      [tool.poe.tasks.serve.args.host]
      options = ["-h", "--host"]
      help = "The host on which to expose the service"
      default = "localhost"

      [tool.poe.tasks.serve.args.port]
      options = ["-p", "--port"]
      help = "The port on which to expose the service"
      default = "8000"

When using this form the *name* option is no longer applicable because the key for the
argument within the args table is taken as the name.


Task argument options
~~~~~~~~~~~~~~~~~~~~~

Named arguments support the following configuration options:

- **default** : Union[str, int, float, bool]
   The value to use if the argument is not provided. This option has no effect if the
   required option is set to true.

- **help** : str
   A short description of the argument to include in the documentation of the task.

- **name** : str
   The name of the task. Only applicable when *args* is an array.

- **options** : List[str]
   A list of options to accept for this argument, similar to
   `argsparse name or flags <https://docs.python.org/3/library/argparse.html#name-or-flags>`_.
   If not provided then the name of the argument is used. You can use this option to
   expose a different name to the CLI vs the name that is used inside the task, or to
   specify long and short forms of the CLI option, e.g. ["-h", "--help"].

- **positional** : bool
   If set to true then the argument becomes a position argument instead of an option
   argument. Note that positional arguments may not have type *bool*.

- **required** : bool
   If true then not providing the argument will result in an error. Arguments are not
   required by default.

- **type** : str
   The type that the provided value will be cast to. The set of acceptable options is
   {"string", "float", "integer", "boolean"}. If not provided then the default behaviour
   is to keep values as strings. Setting the type to "bool" makes the resulting argument
   a flag that if provided will set the value to the boolean opposite of the default
   value – i.e. *true* if no default value is given, or false if :toml:`default = true`.


Arguments for cmd and shell tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For cmd and shell tasks the values are exposed to the task as environment variables. For
example given the following configuration:

.. code-block:: toml

  [tool.poe.tasks.passby]
  shell = """
  echo "hello $planet";
  echo "goodbye $planet";
  """
  help = "Pass by a planet!"

    [[tool.poe.tasks.passby.args]]
    name = "planet"
    help = "Name of the planet to pass"
    default = "earth"
    options = ["-p", "--planet"]

The resulting task can be run like:

.. code-block:: bash

  poe passby --planet mars

Arguments for script tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~

Arguments can be defined for script tasks in the same way, but how they are exposed to
the underlying python function depends on how the script is defined.

In the following example, since no parenthesis are included for the referenced function,
all provided args will be passed to the function as kwargs:

.. code-block:: toml

  [tool.poe.tasks]
  build = { script = "project.util:build", args = ["dest", "version"] }

You can also control exactly how values are passed to the python function as
demonstrated in the following example:

.. code-block:: toml

  [tool.poe.tasks]
  build = { script = "project.util:build(dest, build_version=version, verbose=True)", args = ["dest", "version"]

Arguments for sequence tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Arguments can be passed to the tasks referenced from a sequence task as in the following
example.

.. code-block:: toml

  [tool.poe.tasks]
  build = { script = "util:build_app", args = [{ name = "target", positional = true }] }

  [tool.poe.tasks.check]
  sequence = ["build ${target}", { script = "util:run_tests(environ['target'])" }]
  args = ["target"]

This works by setting the argument values as environment variables for the subtasks,
which can be read at runtime, but also referenced in the task definition as
demonstrated in the above example for a *ref* task and *script* task.

Project-wide configuration options
==================================

Global environment variables
----------------------------

You can configure environment variables to be set for all poe tasks in the
pyproject.toml file by specifying :toml:`tool.poe.env` like so

.. code-block:: toml

  [tool.poe.env]
  VAR1 = "FOO"
  VAR2 = "BAR"

As for the task level option, you can indicated that a variable should only be set if
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

Usage without poetry
====================

Poe the Poet was originally intended for use alongside poetry. But it works just as
well with any other kind of virtualenv, or standalone. This behaviour is configurable
via the :toml:`tool.poe.executor` global option (see above).

By default poe will run tasks in the poetry managed environment, if the pyproject.toml
contains a :toml:`tool.poetry` section. If it doesn't then poe looks for a virtualenv to
use from :bash:`./.venv` or :bash:`./venv` relative to the pyproject.toml file.
Otherwise it falls back to running tasks without any special environment management.


Composing tasks into graphs (Experimental)
==========================================

You can define tasks that depend on other tasks, and optionally capture and reuse the
output of those tasks, thus defining an execution graph of tasks. This is done by using
the *deps* task option, or if you want to capture the output of the upstream task to
pass it to the present task then specify the *uses* option, as demonstrated below.

.. code-block:: toml

  [tool.poe.tasks]
  _website_bucket_name.shell = """
    aws cloudformation describe-stacks \
      --stack-name $AWS_SAM_STACK_NAME \
      --query "Stacks[0].Outputs[?(@.OutputKey == 'FrontendS3Bucket')].OutputValue" \
    | jq -cr 'select(0)[0]'
  """

  [tool.poe.tasks.build-backend]
  help = "Build the backend"
  sequence = [
    {cmd = "poetry export -f requirements.txt --output src/requirements.txt"},
    {cmd = "sam build"},
  ]

  [tool.poe.tasks.build-frontend]
  help = "Build the frontend"
  cmd = "npm --prefix client run build"

  [tool.poe.tasks.shipit]
  help = "Build and deploy the app"
  sequence = [
    "sam deploy --config-env $SAM_ENV_NAME",
    "aws s3 sync --delete ./client/build s3://${BUCKET_NAME}"
  ]
  default_item_type = "cmd"
  deps = ["build-frontend", "build-backend"]
  uses = { BUCKET_NAME = "_website_bucket_name" }

In this example the *shipit* task depends on the *build-frontend* *build-backend*, which
means that these tasks get executed before the *shipit* task. It also declares that it
uses the output of the hidden *_website_bucket_name* task, which means that this also
gets executed, but its output it captured and then made available to the *shipit* task
as the environment variable BUCKET_NAME.

This feature is experimental. There may be edge cases that aren't handled well, so
feedback is requested. Some details of the implementation or API may be altered in
future versions.

Supported python versions
=========================

Poe the Poet officially supports python >3.6.2, and is tested with python 3.6 to 3.9 on
macOS, linux and windows.


Contributing
============

There's plenty to do, come say hi in `the issues <https://github.com/nat-n/poethepoet/issues>`_! 👋

Also check out the `CONTRIBUTING.MD <https://github.com/nat-n/poethepoet/blob/main/.github/CONTRIBUTING.md>`_ 🤓

Licence
=======

MIT.
