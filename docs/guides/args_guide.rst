Configuring CLI arguments
-------------------------

By default extra arguments passed to the poe CLI following the task name are appended to the end of a :doc:`cmd task<../tasks/task_types/cmd>`, or exposed as ``sys.argv`` in a :doc:`script task<../tasks/task_types/script>`, but will cause an error for other task types). Alternatively it is possible to define named arguments that a task should accept, which will be documented in the help for that task, and exposed to the task in a way the makes the most sense for that task type.

In general named arguments can take one of the following three forms:

- **positional arguments** which are provided directly following the name of the task like
   :bash:`poe task-name arg-value`

- **option arguments** which consist of a key and one or more values like
   :bash:`poe task-name --option-name arg-value`

- **flags** which are either provided or not, but don't accept a value like
   :bash:`poe task-name --flag`

The value for the named argument is then accessible by name within the task content,
though exactly how will depend on the type of the task as detailed below.


Configuration syntax
~~~~~~~~~~~~~~~~~~~~

Named arguments are configured by declaring the ``args`` task option as either an array or
a sub-table.


Abbreviated form
""""""""""""""""

The array form may contain string items which are interpreted as an option argument with the given name.

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "myapp:run"
    args = ["host", "port"]

This example can be invoked as

.. code-block:: bash

    poe serve --host 0.0.0.0 --port 8001


Array of inline tables
""""""""""""""""""""""

Items in the array can also be inline tables to allow for more configuration to be provided to the task like so:

.. code-block:: toml

   [tool.poe.tasks.serve]
   cmd = "myapp:run"
   args = [
     { name = "host", default = "localhost" },
     { name = "port", default = "9000" }
   ]


Array of tables
"""""""""""""""

If you want to provide more configuration per argument then the following toml syntax can be used to declare an array of tables with each key on a separate line:

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


.. important::

   The double square brackets is toml syntax for a table within an array.

Subtable configuration syntax
"""""""""""""""""""""""""""""

The following toml syntax structure achieves exactly the same result as the previous example but instead of ``args`` being an array of tables, it is a table of tables like so:

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

When using this form the ``name`` option is no longer applicable because the key for the argument within the args table is taken as the name.


Task argument options
~~~~~~~~~~~~~~~~~~~~~

Named arguments support the following configuration options:

- **default** : ``str`` | ``int`` | ``float`` | ``bool``
   The value to use if the argument is not provided. This option has no significance if the ``required`` option is set to true.

   For string values, environment variables can be referenced using the usual templating syntax as in the following example.

   .. code-block:: toml

     [tool.poe.tasks.deploy]
     cmd = "..."
     env.AWS_REGION.default = "eu-central-1"

     [[tool.poe.tasks.deploy.args]]
     name    = "region"
     help    = "The region to deploy to"
     default = "${AWS_REGION}"

   As in the above example, this can be combined with setting an :doc:`env value<../tasks/options>` on the task with the ``default`` specifier to get the following precedence of values for the arg:

   1. the value passed on the command line
   2. the value of the variable set on the environment
   3. the default value for the environment variable configured on the task

- **help** : ``str``
   A short description of the argument to include in the documentation of the task.

- **name** : ``str``
   The name of the task. Only applicable when *args* is an array.

- **options** : ``list[str]``
   A list of options to accept for this argument, similar to `argsparse name or flags <https://docs.python.org/3/library/argparse.html#name-or-flags>`_. If not provided then the name of the argument is used. You can use this option to expose a different name to the CLI vs the name that is used inside the task, or to specify long and short forms of the CLI option, e.g. ``["-h", "--help"]``.

- **positional** : ``bool``
   If set to true then the argument becomes a position argument instead of an option argument. Note that positional arguments may not have type ``boolean``.

- **multiple** : ``bool`` | ``int``
   If the ``multiple`` option is set to true on a positional or option argument then that argument will accept multiple values.

   If set to a number, then the argument will accept *exactly* that number of values.

   For positional arguments, only the last positional argument may have the ``multiple`` option set.

   This option is not compatible with arguments with type ``boolean`` since these are interpreted as flags. However multiple ones or zeros can be passed to an argument of type "integer" for similar effect.

   The values provided to an argument with the ``multiple`` option set are available on the environment as a string of whitespace separated values. For script tasks, the values will be provided to your python function as a list of values. In a cmd task the values can be passed as separate arguments to the task via templating as in the following example.

   .. code-block:: toml

    [tool.poe.tasks.save]
    cmd  = "echo ${FILE_PATHS}"
    args = [{ name = "FILE_PATHS", positional = true, multiple = true }]

- **required** : ``bool``
   If true then not providing the argument will result in an error. Arguments are not required by default.

- **type** : ``Literal["string", "float", "integer", "boolean"]``
   The type that the provided value will be cast to. If not provided then the default behaviour    is to keep values as strings. Setting the type to ``"boolean"`` makes the resulting argument a flag that if provided will set the value to the boolean opposite of the default value – i.e. :toml:`true` if no default value is given, or :toml:`false` if :toml:`default = true`.

Arguments for cmd and shell tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For :doc:`cmd<../tasks/task_types/cmd>` and :doc:`shell<../tasks/task_types/shell>` tasks the values are exposed to the task as environment variables. For example given the following configuration:

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

.. code-block:: sh

  poe passby --planet mars

.. TIP::
   For PowerShell tasks, the variable needs to be referenced as an environment variable in the shell code, e.g., :code:`$env:planet`.

Arguments for script tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~

Arguments can be defined for :doc:`script<../tasks/task_types/script>` tasks in the same way, but how they are exposed to the underlying python function depends on how the script is defined.

In the following example, since no parenthesis are included for the referenced function, all provided args will be passed to the function as kwargs:

.. code-block:: toml

  [tool.poe.tasks.build]
  script = "my_app.util:build", args = ["dest", "version"]

You can also control exactly how values are passed to the python function as demonstrated in the following example:

.. code-block:: toml

  [tool.poe.tasks.build]
  script = "my_app.util:build(dest, build_version=version, verbose=True)"
  args = ["dest", "version"]

Arguments for sequence tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Arguments can be passed to the tasks referenced from a sequence task as in the following
example.

.. code-block:: toml

  [tool.poe.tasks.build]
  script = "util:build_app"
  args = [{ name = "target", positional = true }]

  [tool.poe.tasks.check]
  sequence = ["build ${target}", { script = "util:run_tests(environ['target'])" }]
  args = ["target"]

This works by setting the argument values as environment variables for the subtasks, which can be read at runtime, but also referenced in the task definition as demonstrated in the above example for a :doc:`ref<../tasks/task_types/ref>` task and :doc:`script<../tasks/task_types/script>` task.

Passing free arguments in addition to named arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If no args are defined for a cmd task then any cli arguments that are provided are simply appended to the command. If named arguments are defined then one can still provide additional free arguments to the command by separating them from the defined arguments with a double dash token :sh:`--`.

For example given a task like:

.. code-block:: toml

  [tool.poe.tasks.lint]
  cmd  = "ruff check ${target_dir}"
  args = { target_dir = { options = ["--target", "-t"], default = "." }}

calling the task like so:

.. code-block:: sh

  poe lint -t tests -- --fix

will result in poe parsing the target_dir cli option, but appending the :sh:`--fix` flag to the ruff command without attempting to interpret it.

.. note::

   Passing :sh:`--` in the arguments list to any other task type will simply result in any subsequent arguments being ignored.
