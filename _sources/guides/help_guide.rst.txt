Documenting tasks
=================

You can add help text to your tasks by adding the ``help`` option to the task definition, like so:

.. code-block:: toml

  [tool.poe.tasks.test]
  help = "Run the test suite"
  cmd  = "pytest --cov=poethepoet"

  [tool.poe.tasks.serve]
  help   = "Run the app in debug mode"
  script = "my_app.service:run(debug=True)"

  [tool.poe.tasks.tunnel]
  help  = "Create an SSH tunnel to the production server"
  shell = "ssh -N -L 0.0.0.0:8080:$prod_host:8080 $prod_host &"
  args   = [
    {name = "prod_host", help = "Hostname of the production server", default = "myapp.com"}
  ]

This help text will be displayed alongside the task name in the list of configured tasks when ``poe`` is run without specifying a task.

.. code-block:: docs

  $ poe --help
  Poe the Poet - A task runner that works well with poetry.
  version 0.25.1

  Usage:
    poe [global options] task [task arguments]

  Global options:
    -h [TASK], --help [TASK]
                          Show this help page and exit, optionally supply a task.
    --version             Print the version and exit
    -v, --verbose         Increase command output (repeatable)
    -q, --quiet           Decrease command output (repeatable)
    -d, --dry-run         Print the task contents but don't actually run it
    -C PATH, --directory PATH
                          Specify where to find the pyproject.toml
    -e EXECUTOR, --executor EXECUTOR
                          Override the default task executor
    --ansi                Force enable ANSI output
    --no-ansi             Force disable ANSI output

  Configured tasks:
    test           Run the test suite
    serve          Run the app in debug mode
    tunnel         Create an SSH tunnel to the production server
      --prod_host  Hostname of the production server [default: myapp.com]

Display help for a single task
------------------------------

Passing the ``--help`` option normally has the same effect as running poe with no arguments. However you can also supply the name of a task to display documentation for just that task.

.. code-block:: docs

  $ poe --help tunnel

  Description:
    Create an SSH tunnel to the production server

  Usage:
    poe [global options] tunnel [named arguments] -- [free arguments]

  Named arguments:
    --prod_host    Hostname of the production server [default: myapp.com]
