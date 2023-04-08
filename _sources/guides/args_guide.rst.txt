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
