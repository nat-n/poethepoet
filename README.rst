************
Poe the Poet
************

A task runner that works well with poetry.

.. role:: sh(code)
   :language: sh
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

|•| Can be used standalone or as a poetry plugin

|•| Tasks can be commands (with or without a shell) or references to python functions (like tool.poetry.scripts)

|•| Short and sweet commands with extra arguments passed to the task :bash:`poe [options] task [task_args]`, or you can define arguments explicitly.

|•| Tasks can specify and reference environment variables as if they were evaluated by a shell

|•| Tasks are self documenting, with optional help messages (just run poe without arguments)

|•| Tasks can be defined as a sequence of other tasks

|•| Works with .env files


Installation
============

1.
  Install the CLI

  .. code-block:: bash

    pipx install poethepoet

  Or use pip to install into any python environment

  .. code-block:: bash

    pip install poethepoet

2.
  Or into your project (so it works inside poetry shell):

  .. code-block:: bash

    poetry add --group dev poethepoet

3.
  Or into poetry as a plugin (requires poetry >= 1.2)

  .. code-block:: bash

    poetry self add 'poethepoet[poetry_plugin]'

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

Or use it as a poetry plugin (for poetry >= 1.2) like so

.. code-block:: bash

  poetry self add poethepoet[poetry_plugin]
  poetry poe [options] task [task_args]

Or just install it as a dev dependency with poetry and run it like

.. code-block:: bash

  poetry add --group dev poethepoet
  poetry run poe [options] task [task_args]

Though in that case you might like to define :bash:`alias poe='poetry run poe'`.

Types of task
=============

There are seven types of task:

- **Command tasks (cmd)**: for simple commands that are executed as a subprocess without a shell
- **Script tasks (script)**: for python function calls
- **Shell tasks (shell)**: for scripts to be executed with via an external interpreter (such as sh).
- **Sequence tasks (sequence)**: for composing multiple tasks into a sequence
- **Expression tasks (expr)**: which consist of a python expression to evaluate
- **Switch tasks (switch)**: for running different tasks depending on a control value (such as the platform)
- **Ref tasks (ref)**: used for defining a task as an alias of another task, such as in a sequence task.

The default task type is cmd.

'cmd' tasks
-----------

**Command tasks** contain a single command that will be executed without a shell.
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

'script' tasks
--------------

**Script tasks** consist of a reference to a python callable to import and execute, and optionally values or expressions to pass as arguments, for example:

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

Calling standard library functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Any python callable accessible via the python path can be referenced, including the
standard library. This can be useful for ensuring that tasks work across platforms.

For example, the following task will not always work on windows:

.. code-block:: toml

  [[tool.poe.tasks.build]]
  cmd = "mkdir -p build/assets"

whereas the same behaviour can can be reliably achieved like so:

.. code-block:: toml

  [[tool.poe.tasks.build]]
  script = "os:makedirs('build/assets', exist_ok=True)"

Output the return value from the python callable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Script tasks can be configured to output the return value of a callable using the
:toml:`print_result` option like so:

.. code-block:: toml

  [tool.poe.tasks.create-secret]
  script = "django.core.management.utils:get_random_secret_key()"
  print_result = true

Given the above configuration running the following command would output just the
generated key.

.. code-block:: bash

  poe -q create-secret

Note that if the return value is None then the :toml:`print_result` option has no
effect.

'shell' tasks
-------------

Shell tasks are similar to simple command tasks except that they are executed
inside a new shell, and can consist of multiple statements. This means they can leverage
the full syntax of the shell interpreter such as command substitution, pipes, background
processes, etc.

An example use case for this might be opening some ssh tunnels in the background with
one task and closing them with another like so:

.. code-block:: toml

  [tool.poe.tasks]
  pfwd = { "shell" = "ssh -N -L 0.0.0.0:8080:$STAGING:8080 $STAGING & ssh -N -L 0.0.0.0:5432:$STAGINGDB:5432 $STAGINGDB &" }
  pfwdstop = { "shell" = "kill $(pgrep -f "ssh -N -L .*:(8080|5432)")" }

By default poe attempts to find a posix shell (sh, bash, or zsh in that order) on the
system and uses that. When running on windows, poe will first look for
`Git bash <https://gitforwindows.org>`_ at the usual location, and otherwise attempt to
find it via the PATH, though this might not always be possible.

Using different types of shell/interpreter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is also possible to specify an alternative interpreter (or list of compatible
interpreters ordered by preference) to be invoked to execute shell task content. For
example if you only expect the task to be executed on windows or other environments
with powershell installed then you can specify a powershell based task like so:

.. code-block:: toml

  [tool.poe.tasks.install-poetry]
  shell = """
  (Invoke-WebRequest -Uri https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py -UseBasicParsing).Content | python -
  """
  interpreter = "pwsh"

If your task content is restricted to syntax that is valid for both posix shells and
powershell then you can maximise the likelihood of it working on any system by
specifying the interpreter as:

.. code-block:: toml

  interpreter = ["posix", "pwsh"]

It is also possible to specify python code as the shell task code as in the following
example. However it is recommended to use a *script* task rather than writing complex
code inline within your pyproject.toml.

.. code-block:: toml

  [tool.poe.tasks.time]
  shell = """
  from datetime import datetime

  print(datetime.now())
  """
  interpreter = "python"

The following interpreter values may be used:

posix
    This is the default behavoir, equivalent to ["sh", "bash", "zsh"], meaning that
    poe will try to find sh, and fallback to bash, then zsh.
sh
    Use the basic posix shell. This is often an alias for bash or dash depending on
    the operating system.
bash
    Uses whatever version of bash can be found. This is usually the most portable option.
zsh
    Uses whatever version of zsh can be found.
fish
    Uses whatever version of fish can be found.
pwsh
    Uses powershell version 6 or higher.
powershell
    Uses the newest version of powershell that can be found.

The default value can be changed with the global *shell_interpreter* option as
described below.

'sequence' tasks
----------------

Sequence tasks are defined as a array of other tasks to be run one after the other.

By default the contents of the array are interpreted as references to other tasks
(actually a ref task type), though this behaviour can be altered by setting the global
:toml:`default_array_item_task_type` option to the name of another task type such as
*cmd*, or by setting the :toml:`default_item_type` option locally on the sequence task.

Sequence task with references
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

  [tool.poe.tasks]

  test = "pytest --cov=src"
  build = "poetry build"
  _publish = "poetry publish"
  release = ["test", "build", "_publish"]

Note that tasks with names prefixed with :code:`_` are not included in the
documentation or directly executable, but can be useful for cases where a task is only
needed for referencing from another task.

Sequence task with inline tasks expressed via inline tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

  release = [
    { cmd = "pytest --cov=src" },
    { script = "devtasks:build" },
    { ref = "_publish" },
  ]

Sequence task with inline tasks expressed via an array of tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

  [tool.poe.tasks]

    [[tool.poe.tasks.release]]
    cmd = "pytest --cov=src"

    [[tool.poe.tasks.release]]
    script = "devtasks:build"

    [[tool.poe.tasks.release]]
    ref = "_publish"

Sequence task with inline script subtasks using default_item_type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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


'expr' tasks
------------

Expr tasks consist of a single `python expression <https://docs.python.org/3/reference/expressions.html>`_. Running the task evaluates the expression and outputs the resulting
value. Here's a trivial example of an expr task that will print 2 when run:

.. code-block:: toml

  [tool.poe.tasks.trivial-example]
  expr = "1 + 1"

.. code-block:: bash

  $ poe trivial-example
  Poe => 1 + 1
  2

Expressions can:

- use most python expression constructs with the exception of yield, await, or named
  expressions
- use most builtin functions including all members of
  `this collection <https://github.com/nat-n/poethepoet/blob/main/poethepoet/helpers/python.py#L13>`_
- reference the sys module without having to specify it as an import
- reference sys.argv to get whatever arguments were passed to the task, just like in
  script tasks
- referene values of named args as python variables
- include environment variables as string values that are injected into the expression
  using the usual templating syntax

Referencing arguments and environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The expression can reference environment variables using templating syntax like in cmd
tasks, and named arguments as python variables in scope like in script tasks.

.. code-block:: toml

  [tool.poe.tasks.venv-active]
  expr = """(
    f'{target_venv} is active'
    if ${VIRTUAL_ENV}.endswith(target_venv)
    else f'{target_venv} is not active'
  )"""
  args = [{ name = "target-venv", default = ".venv", positional = true }]

.. code-block::

  $ poe venv-active poethepoet-LCpCQf8S-py3.10
  Poe => (
    f'{target_venv} is active'
    if ${VIRTUAL_ENV}.endswith(target_venv)
    else f'{target_venv} is not active'
  )
  poethepoet-LCpCQf8S-py3.10 is not active

In this example the :code:`VIRTUAL_ENV` environment variable is templated into the
expression using the usual templating syntax, and the :code:`target_venv` argument is
referenced directly as a variable.

Notice that the expression may be formatted over multiple lines, as in normal python
code.

Referencing imported modules in an expression
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default the sys module is available to the expression which allows access to sys.argv
or sys.platform amoung other useful values. However you can also reference any other
importable module via the imports option as in the following example.

.. code-block:: toml

  [tool.poe.tasks.count-hidden]
  help    = "Count hidden files or subdirectories"
  expr    = "len(list(pathlib.Path('.').glob('.*')))"
  imports = ["pathlib"]

Fail if the expression result is falsey
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The expression can be made to behave like an assertion that fails if the result is not truthy by providing the assert option. The task defined in the following example will
return non-zero if the result is False.

.. code-block:: toml

  [tool.poe.tasks.venv-active]
  expr   = "${VIRTUAL_ENV}.endswith(target_venv)"
  assert = true
  args   = [{ name = "target-venv", default = ".venv", positional = true }]

Referencing the result of other tasks in an expression
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Expr tasks can reference the results of other tasks by leveraging the :code:`uses`
option.

.. code-block:: toml

  [tool.poe.tasks._get_active_session]
  cmd = "read_session --format json"

  [tool.poe.tasks.show-user]
  expr    = """(
    f"User: {json.loads(${SESSION_JSON})['User']}"
    if len(${SESSION_JSON}) > 2
    else "No active session."
  )"""
  uses    = { SESSION_JSON = "_get_active_session" }
  imports = ["json"]


'switch' tasks
--------------

Much like a switch statement in many programming languages, a switch task consists of a
control task and a array of tasks to switch between. The control task is run first, and
its output is captured and matched against the case option of each of the items in the
switch array to determine which one to run.

This can be used to define a task that runs a different subtask depending on which
platform it is running on like so:

.. code-block:: toml

  [tool.poe.tasks.build]
  control.expr = "sys.platform"

    [[tool.poe.tasks.platform_dependent.switch]]
    case = "win32"
    cmd  = "windows_build"

    [[tool.poe.tasks.platform_dependent.switch]]
    cmd  = "posix_build"

In the above example the control task checks the value of sys.platform, and if running
on windows it'll execute :toml:`windows_build`, otherwise it'll fall back to the default
case (i.e. the switch item with no case option defined) and execute :toml:`posix_build`.

Multiple values per case
~~~~~~~~~~~~~~~~~~~~~~~~

It is also possible to define multiple values for a single case option by providing a
array of values like so:

.. code-block:: toml

    [[tool.poe.tasks.platform_dependent.switch]]
    case = ["linux", "darwin"]
    cmd  = "build"

Don't fail if there's no match
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If all tasks in the switch array include a case value, but none of them match the result
of the control task then by default the switch task will fail. You can instead configure
the switch task to pass and simply do nothing by providing the 'default' option like so:

.. code-block:: toml

  [tool.poe.tasks.build_on_windows]
  control.expr = "sys.platform"
  default = "pass"

    [[tool.poe.tasks.platform_dependent.switch]]
    case = "win32"
    cmd  = "build"

Switching on an environment variable or named argument
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to run a different task depending on the value of an environment variable
as in the following example.

.. code-block:: toml

  [tool.poe.tasks.check_number]
  control.expr = "int(${BEST_NUMBER}) % 2"

    [[tool.poe.tasks.check_number.switch]]
    case = "0"
    expr = "f'{${BEST_NUMBER}} is even')"

    [[tool.poe.tasks.check_number.switch]]
    case = "1"
    expr = "f'{${BEST_NUMBER}} is odd'"

Using this task will look like the following:

.. code-block:: sh

  $ BEST_NUMBER=12 poe check_number
  Poe <= int(${BEST_NUMBER}) % 2
  Poe => f'{${BEST_NUMBER}} is even')
  12 is even

  $ BEST_NUMBER=17 poe check_number
  Poe <= int(${BEST_NUMBER}) % 2
  Poe => f'{${BEST_NUMBER}} is odd'
  17 is odd

You can also run a different task depending on the value of a named argument as in the following example.

.. code-block:: toml

  [tool.poe.tasks.icecream]
  control.expr = "flavor"
  args = ["flavor"]

    [[tool.poe.tasks.icecream.switch]]
    case = "chocolate"
    cmd  = "make_chocolate_icecream"

    [[tool.poe.tasks.icecream.switch]]
    case = "strawberry"
    cmd  = "make_strawberry_icecream"

    [[tool.poe.tasks.icecream.switch]]
    cmd  = "make_vanilla_icecream"


'ref' tasks
-----------

A ref task is essentially a call to another task. It is the default task type within a sequence task, but is not often used otherwise.

A ref task can set environment variables, and pass arguments to the referenced task as
follows:

.. code-block:: toml

  [tool.poe.tasks]
  do_things.cmd = "do_cmd"
  do_things.args = [{ name = "things", multiple = true, positional = true }]

  do_specific_things.ref = "do_things thing1 thing2"
  do_specific_things.env = { URGENCY = "11" }


In the above example calling:

.. code-block:: sh

  poe do_specific_things

would be equivalent to executing the following in the shell:

.. code-block:: sh

  URGENCY=11 do_cmd thing1 thing2


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
supported by some older toml implementations.

The above example can be modified to only set the `PORT` variable if it is not already
set by replacing the last line with the following:

.. code-block:: toml

    serve.env.PORT.default = "9001"


Loading env vars from an env file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also specify one or more env files (with bash-like syntax) to load per task like so:

.. code-block:: bash

    # .env
    STAGE=dev
    PASSWORD='!@#$%^&*('

.. code-block:: toml

    [tool.poe.tasks]
    serve.script  = "myapp:run"
    serve.envfile = ".env"

The envfile option accepts the name (or relative path) to a single envfile as shown
above but can also by given a list of such paths like so:

.. code-block:: toml

    serve.envfile = [".env", "local.env"]

In this case the referenced files will be loaded in the given order.

Defining env vars in terms of other env vars
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is also possible to reference existing env vars when defining a new env var for a
task. This may be useful for aliasing or extending a variable already defined in the
host environment, globally in the config, or in a referenced envfile. In the following
example the value from $TF_VAR_service_port on the host environment is also made
available as $FLASK_RUN_PORT within the task.

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "flask run"
    env = { FLASK_RUN_PORT = "${TF_VAR_service_port}" }

Running a task with a specific working directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default tasks are run from the project root – that is the parent directory of the
pyproject.toml file. However if a task needs to be run in another directory within the
project then this can be accomplished by using the :toml:`cwd` option like so:

.. code-block:: toml

    [tool.poe.tasks.build-client]
    cmd = "npx ts-node -T ./build.ts"
    cwd = "./client"

In this example, the npx executable is executed inside the :sh:`./client` subdirectory of
the project, and will use the nodejs package.json configuration from that location and
evaluate paths relative to that location.

Defining tasks that run via exec instead of a subprocess
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Normally tasks are executed as subprocesses of the poe cli. This makes it possible for
poe to run multiple tasks, for example within a sequence task or task graph.

However in certain situations it can be desirable to define a task that is instead
executed within the same process via exec. Cmd and script tasks can be configured to
work this way using the :toml:`use_exec` option like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd      = "gunicorn ./my_app:run"
    use_exec = true

Note the following limitations with this feature:

- a task configured in this way may not be referenced by another task

- this does not work on windows becuase of `this issue <https://bugs.python.org/issue19066>`_. On windows a subprocess is always created.

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
   The value to use if the argument is not provided. This option has no significance if
   the required option is set to true.

   For string values, environment variables can be referenced using the usual templating
   syntax as in the following example.

   .. code-block:: toml

    [[tool.poe.tasks.deploy.args]]
    name    = "region"
    help    = "The region to deploy to"
    default = "${AWS_REGION}"

   This can be combined with setting an env values on the task with the default
   specifier to get the following precendence of values for the arg:

   1. the value passed on the command line
   2. the value of the variable set on the environment
   3. the default value for the environment variable configured on the task

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

- **multiple** : Union[bool, int]
   If the multiple option is set to true on a positional or option argument then that
   argument will accept multiple values.

   If set to a number, then the argument will accept exactly that number of values.

   For positional aguments, only the last positional argument may have the multiple
   option set.

   The multiple option is not compatible with arguments with type boolean since
   these are interpreted as flags. However multiple ones or zeros can be passed to an
   argument of type "integer" for similar effect.

   The values provided to an argument with the multiple option set are available on
   the environment as a string of whitespace separated values. For script tasks, the
   values will be provided to your python function as a list of values. In a cmd task
   the values can be passed as separate arugments to the task via templating as in the
   following example.

   .. code-block:: toml

    [tool.poe.tasks.save]
    cmd  = "echo ${FILE_PATHS}"
    args = [{ name = "FILE_PATHS", positional = true, multiple = true }]

- **required** : bool
   If true then not providing the argument will result in an error. Arguments are not
   required by default.

- **type** : str
   The type that the provided value will be cast to. The set of acceptable options is
   {"string", "float", "integer", "boolean"}. If not provided then the default behaviour
   is to keep values as strings. Setting the type to "boolean" makes the resulting
   argument a flag that if provided will set the value to the boolean opposite of the
   default value – i.e. *true* if no default value is given, or false if
   :toml:`default = true`.


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

Load tasks from another file
============================

There are some scenarios where one might wish to define tasks outside of pyproject.toml,
or to collect tasks from multiple projects into one. For example, if you want to share
tasks between projects via git modules, generate tasks definitions dynamically, organise
your code in a monorepo, or simply have a lot of tasks and don't want the pyproject.toml
to get too large. This can be achieved by creating a toml or json including the same
structure for tasks as used in pyproject.toml

For example:

.. code-block:: toml

  # acme_common/shared_tasks.toml
  [tool.poe.tasks.build-image]
  cmd = "docker build"


.. code-block:: toml

  [tool.poe]
  # this references a file from a git submodule
  include = "modules/acme_common/shared_tasks.toml"

Imported files may also specify environment variables via
:code:`tool.poe.envfile` or entries for :code:`tool.poe.env`.

It's also possible to include tasks from multiple files by providing a list like
so:

.. code-block:: toml

  [tool.poe]
  include = ["modules/acme_common/shared_tasks.toml", "generated_tasks.json"]

Files are loaded in the order specified. If an item already exists then the included
value it ignored.

If an included task file itself includes other files, these second order includes are
not inherited, so circular includes don't cause any problems.

When including files from another location, you can also specify that tasks from that
other file should be run from within a specific directory. For example with the
following configuration, when tasks imported from my_subproject are run
from the root, the task will actually execute as if it had been run from the
my_subproject subdirectory.

.. code-block:: toml

  [[tool.poe.include]]
  path = "my_subproject/pyproject.toml"
  cwd  = "my_subproject"

The cwd option still has the limitation that it cannot be used to specify a directory
outside of parent directory of the pyproject.toml file that poe is running with.

If a referenced file is missing then poe ignores it without error, though
failure to read the contents will result in failure.

Usage as a poetry plugin
========================

Depending on how you manage your python environments you may also wish to use Poe the
Poet in the form of a poetry plugin. This requires installing `poethepoet[poetry_plugin]`
either into the same environment as poetry or into poetry itself.
`See the poetry docs <https://python-poetry.org/docs/master/plugins/#using-plugins>`_
for more details.

Due to how the poetry CLI works (using `cleo <https://github.com/sdispater/cleo>`_ — a
featureful but highly opinionated  CLI framework) there exist a few minor limitations
when used in this way.

1.
  Normally the poe CLI allows tasks to accept any arguments, either by defining the
  expected options or by passing any command line tokens following the task name to the
  task at runtime. This is not supported by cleo. The plugin implements a workaround
  that mostly works, but still if the `--no-plugins` option is provided *anywhere* in
  the command line then the poe plugin will never be invoked.

2.
  Poetry comes with its own
  `command line completion <https://python-poetry.org/docs/#enable-tab-completion-for-bash-fish-or-zsh>`_,
  but poe's command line completion won't work.

3.
  If you declare named arguments for your poe tasks then these are included in the
  documentation when poe is invoked without any arguments. However the inline
  documentation for poetry commands contains only the task names and help text.

Therefore it is recommended to use the poe CLI tool directly if you don't mind having
it installed onto your path.

Configuring the plugin
----------------------

By default the poetry plugin will register *poe* as a command prefix so tasks can be
invoked like:

.. code-block:: sh

  poetry poe [task_name] [task_args]

And the poe documentation can be viewed via:

.. code-block:: bash

  poetry poe

It is also possible to modify this behavoir, to either have a different command prefix
or none at all by setting the :toml:`poetry_command` global option in your
pyproject.toml like so:

.. code-block:: toml

  [tool.poe]
  poetry_command = ""

In this case poe tasks will be registered as top level commands on poetry and can be
invoked simply as:

.. code-block:: sh

  poetry [task_name]

.. warning::
    Whatever :toml:`tool.poe.poetry_command` is set to must not already exist as a
    poetry command!

    Additionally if setting it to the emtpy string then care must be taken to avoid
    defining any poe tasks that conflict with any other built in or plugin provided
    poetry command.

Hooking into poetry commands
----------------------------

It is also possible to configure a task to be run before or after a specific poetry
command by declaring the poetry_hooks global option like so:

.. code-block:: toml

  [tool.poe.poetry_hooks]
  pre_build  = "prep-assets --verbosity=5"
  post_build = "archive-build"

  [tool.poe.tasks.prep-assets]
  script = "scripts:prepare_assets"
  help   = "Optimise static assets for inclusion in the build"

  [tool.poe.tasks.archive-build]
  script = "scripts:archive_build"
  help   = "Upload the latest build version to archive server"

In this example the :code:`prep-assets` task will be run as the first step in calling
:bash:`poetry build` with an argument passed as if the task were being called via the
poe CLI. We've also configured the :code:`archive-build` task to be run after every
successful build.

If a task fails when running as a hook, then the poetry command will exit with an error.
If it is a *pre* hook then this will cause the actual poetry command not to execute.
This behaviour may be useful for running checks before :bash:`poetry publish`

Hooks can be disabled for a single invocation by passing the :bash:`--no-plugins` option
to poetry.

Namespaced commands like :bash:`poetry env info` can be specified with underscores like so:

.. code-block:: toml

  [tool.poe.poetry_hooks]
  post_env_info = "info"


Usage without poetry
====================

Poe the Poet was originally intended for use alongside poetry. But it works just as
well with any other kind of virtualenv, or simply as a general purpose way to define
handy tasks for use within a certain directory structure! This behaviour is configurable
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

Note that captured output that is exposed as an environment variable via the `uses`
is compacted to have new lines removed. This is similar to how interpolated command
output is treated by bash.

This feature is experimental. There may be edge cases that aren't handled well, so
feedback is requested. Some details of the implementation or API may be altered in
future versions.

Supported python versions
=========================

Poe the Poet officially supports python >=3.7, and is tested with python 3.7 to 3.11 on
macOS, linux and windows.

Contributing
============

There's plenty to do, come say hi in
`the issues <https://github.com/nat-n/poethepoet/issues>`_! 👋

Also check out the
`CONTRIBUTING.MD <https://github.com/nat-n/poethepoet/blob/main/.github/CONTRIBUTING.md>`_ 🤓

Licence
=======

MIT.
