Standard task options
=====================

Overview
--------

The following options can be configured on your tasks and are not specific to any particular task type.

**help** : ``str`` | ``int`` :ref:`📖<Documenting tasks>`
  Help text to be displayed next to the task name in the documentation when poe is run without specifying a task.

**args** : ``Dict[str, dict]`` | ``List[Union[str, dict]]`` :ref:`📖<Declaring CLI arguments>`
  Define CLI options, positional arguments, or flags that this task should accept.

**env** :  ``Dict[str, str]`` :ref:`📖<Setting task specific environment variables>`
  A map of environment variables to be set for this task.

**envfile** :  ``str`` | ``List[str]`` :ref:`📖<Loading environment variables from an env file>`
  Provide one or more env files to be loaded before running this task.

**cwd** :  ``str`` :ref:`📖<Running a task with a specific working directory>`
  Specify the current working directory that this task should run with. The given path is resolved relative to the parent directory of the ``pyproject.toml``.

**deps** :  ``List[str]`` :doc:`📖<../guides/composition_guide>`
  A list of task invocations that will be executed before this one.

**uses** :  ``Dict[str, str]`` :doc:`📖<../guides/composition_guide>`
  Allows this task to use the output of other tasks which are executed first.
  The value is a map where the values are invocations of the other tasks, and the keys are environment variables by which the results of those tasks will be accessible in this task.

**use_exec** : ``bool`` :ref:`📖<Defining tasks that run via exec instead of a subprocess>`
  Specify that this task should be executed in the same process, instead of as a subprocess.

  .. attention::

    This option is only applicable to **cmd** and **script** tasks, and it implies the task in question cannot be referenced by another task.

Documenting tasks
-----------------

You can add help text to your tasks by adding the ``help`` option to the task definition, like so:

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

This help text will be displayed alongside the task name in the list of configured tasks when ``poe`` is run without specifying a task.

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

- **default** : ``str`` | ``int`` | ``float`` | ``bool``
   The value to use if the argument is not provided. This option has no significance if the required option is set to true.

   For string values, environment variables can be referenced using the usual templating syntax as in the following example.

   .. code-block:: toml

    [[tool.poe.tasks.deploy.args]]
    name    = "region"
    help    = "The region to deploy to"
    default = "${AWS_REGION}"

   This can be combined with setting an env values on the task with the default specifier to get the following precendence of values for the arg:

   1. the value passed on the command line
   2. the value of the variable set on the environment
   3. the default value for the environment variable configured on the task

- **help** : ``str``
   A short description of the argument to include in the documentation of the task.

- **name** : ``str``
   The name of the task. Only applicable when *args* is an array.

- **options** : ``List[str]``
   A list of options to accept for this argument, similar to `argsparse name or flags <https://docs.python.org/3/library/argparse.html#name-or-flags>`_. If not provided then the name of the argument is used. You can use this option to expose a different name to the CLI vs the name that is used inside the task, or to specify long and short forms of the CLI option, e.g. ["-h", "--help"].

- **positional** : ``bool``
   If set to true then the argument becomes a position argument instead of an option argument. Note that positional arguments may not have type *bool*.

- **multiple** : ``bool`` | ``int``
   If the multiple option is set to true on a positional or option argument then that argument will accept multiple values.

   If set to a number, then the argument will accept exactly that number of values.

   For positional aguments, only the last positional argument may have the multiple option set.

   The multiple option is not compatible with arguments with type boolean since these are interpreted as flags. However multiple ones or zeros can be passed to an argument of type "integer" for similar effect.

   The values provided to an argument with the multiple option set are available on the environment as a string of whitespace separated values. For script tasks, the values will be provided to your python function as a list of values. In a cmd task the values can be passed as separate arugments to the task via templating as in the following example.

   .. code-block:: toml

    [tool.poe.tasks.save]
    cmd  = "echo ${FILE_PATHS}"
    args = [{ name = "FILE_PATHS", positional = true, multiple = true }]

- **required** : ``bool``
   If true then not providing the argument will result in an error. Arguments are not required by default.

- **type** : ``str``
   The type that the provided value will be cast to. The set of acceptable options is    {"string", "float", "integer", "boolean"}. If not provided then the default behaviour    is to keep values as strings. Setting the type to "boolean" makes the resulting    argument a flag that if provided will set the value to the boolean opposite of the    default value – i.e. *true* if no default value is given, or false if :toml:`default = true`.

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

Passing free arguments in addition to named arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If no args are defined for a cmd task then any cli arguments that are provided are
simply appended to the command. If named arguments are defined then one can still
provide additional free arguments to the command by separating them from the defined
arguments with a double dash token :sh:`--`.

For example given a task like:

.. code-block:: toml

  [tool.poe.tasks.lint]
  cmd  = "ruff check ${target_dir}"
  args = { target_dir = { options = ["--target", "-t"], default = "." }}

calling the task like so:

.. code-block:: sh

  poe lint -t tests -- --fix

will result in poe parsing the target_dir cli option, but appending the :sh:`--fix`
flag to the ruff command without attempting to interpret it.

Passing :sh:`--` in the arguments list to any other task type will simple result in any
subsequent arguments being ignored.

Setting task specific environment variables
-------------------------------------------

You can specify arbitrary environment variables to be set for a single task by providing the env option like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    script = "myapp:run"
    env = { PORT = "9001" }

Notice this example uses deep keys which can be more convenient but aren't as well supported by some older toml implementations.


Setting defaults for environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The previous example can be modified to only set the `PORT` variable if it is not already set by replacing the last line with the following:

.. code-block:: toml

    env.PORT.default = "9001"


Templating environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is also possible to reference existing environment variables when defining a new environment variable for a task. This may be useful for aliasing or extending a variable already defined in the host environment, globally in the config, or in a referenced envfile. In the following example the value from $TF_VAR_service_port on the host environment is also made available as $FLASK_RUN_PORT within the task.

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "flask run"
    env = { FLASK_RUN_PORT = "${TF_VAR_service_port}" }


Loading environment variables from an env file
----------------------------------------------

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


Running a task with a specific working directory
------------------------------------------------

By default tasks are run from the project root – that is the parent directory of the pyproject.toml file. However if a task needs to be run in another directory within the project then this can be accomplished by using the :toml:`cwd` option like so:

.. code-block:: toml

    [tool.poe.tasks.build-client]
    cmd = "npx ts-node -T ./build.ts"
    cwd = "./client"

In this example, the npx executable is executed inside the :sh:`./client` subdirectory of the project, and will use the nodejs package.json configuration from that location and evaluate paths relative to that location.


Defining tasks that run via exec instead of a subprocess
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Normally tasks are executed as subprocesses of the ``poe`` executable. This makes it possible for poe to run multiple tasks, for example within a sequence task or task graph.

However in certain situations it can be desirable to define a task that is instead executed within the same process via an *exec* call. :doc:`task_types/cmd` and :doc:`task_types/script` tasks can be configured to work this way using the :toml:`use_exec` option like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd      = "gunicorn ./my_app:run"
    use_exec = true

.. warning::

  Note the following limitations with this feature:

  1. a task configured in this way may not be referenced by another task
  2. this does not work on windows becuase of `this issue <https://bugs.python.org/issue19066>`_. On windows a subprocess is always created.
