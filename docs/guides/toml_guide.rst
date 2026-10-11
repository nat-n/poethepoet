Using toml syntax
=================

TOML offers several equivalent ways of writing the same structure, so the same task can be defined more tersely or more expressively depending on how much configuration it needs. Poe the Poet only cares about the resulting structure, so you can choose whichever style reads best for each task.

For example, the following definitions of a task with a help message and an argument are all equivalent.

Using a table per task:

.. code-block:: toml

  [tool.poe.tasks.serve]
  help = "Run the development server"
  cmd  = "flask run --port ${port}"
  args = [{ name = "port", default = "5000" }]

Using an inline table:

.. code-block:: toml

  [tool.poe.tasks]
  serve = { help = "Run the development server", cmd = "flask run --port ${port}", args = [{ name = "port", default = "5000" }] }

Using dotted keys:

.. code-block:: toml

  [tool.poe.tasks]
  serve.help = "Run the development server"
  serve.cmd  = "flask run --port ${port}"
  serve.args = [{ name = "port", default = "5000" }]

Using a sub-table for args, and an array of tables for each arg:

.. code-block:: toml

  [tool.poe.tasks.serve]
  help = "Run the development server"
  cmd  = "flask run --port ${port}"

    [[tool.poe.tasks.serve.args]]
    name    = "port"
    default = "5000"

.. tip::

  The indentation in the last example is optional, but can make it clearer which table the args belong to.

Tasks that don't need any options besides their content can be defined most succinctly as a string (interpreted as a :doc:`cmd task<../tasks/task_types/cmd>` by default) or an array (interpreted as a :doc:`sequence task<../tasks/task_types/sequence>` by default):

.. code-block:: toml

  [tool.poe.tasks]
  test  = "pytest"
  check = ["lint", "test"]

Strings containing quotes or backslashes, or spanning multiple lines, are often easier to write using TOML's literal strings (single quotes) or multi-line strings (triple quotes):

.. code-block:: toml

  [tool.poe.tasks]
  greet = 'echo "Hello, world!"'
  build.shell = """
    rm -rf dist
    poetry build
  """

Note that within a basic (double-quoted) TOML string a backslash must itself be escaped, e.g. ``greet = "echo Hello \\$USER"`` passes ``\$USER`` to poe, which prevents the variable from being expanded.

.. seealso::

  See the |toml_spec_link| for full details of the TOML syntax.

.. |toml_spec_link| raw:: html

   <a href="https://toml.io/en/v1.0.0" target="_blank">TOML specification</a>
