Using toml syntax
=================

TOML offers several equivalent ways of writing the same structure, so a task can be defined more tersely or more expressively depending on how much configuration it needs. Poe the Poet only sees the resulting structure, so you can choose whichever style reads best for each task.

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

Using an array of tables for the args:

.. code-block:: toml

  [tool.poe.tasks.serve]
  help = "Run the development server"
  cmd  = "flask run --port ${port}"

  [[tool.poe.tasks.serve.args]]
  name    = "port"
  default = "5000"

Strings containing quotes or backslashes are often easier to write as TOML literal strings (single quotes), and longer commands or scripts as multi-line strings (triple quotes):

.. code-block:: toml

  [tool.poe.tasks]
  greet = 'echo "Hello, world!"'
  build.shell = """
    rm -rf dist
    poetry build
  """

Within a basic (double quoted) string a backslash must itself be escaped, so for example ``greet = "echo Hello \\$USER"`` passes ``echo Hello \$USER`` to poe, which prevents the variable from being expanded.

See the |toml_spec_link| for full details of the TOML syntax.

.. |toml_spec_link| raw:: html

   <a href="https://toml.io/en/v1.0.0" target="_blank">TOML specification</a>
