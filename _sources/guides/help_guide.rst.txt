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

.. code-block:: docs

  $ poe --help
  Poe the Poet - A task runner that works well with poetry.
  version 0.25.1

  USAGE
    poe [-h] [-v | -q] [-C PATH] [--ansi | --no-ansi] task [task arguments]

  GLOBAL OPTIONS
    -h, --help            Show this help page and exit
    --version             Print the version and exit
    -v, --verbose         Increase command output (repeatable)
    -q, --quiet           Decrease command output (repeatable)
    -d, --dry-run         Print the task contents but don't actually run it
    -C PATH, --directory PATH
                          Specify where to find the pyproject.toml
    --ansi                Force enable ANSI output
    --no-ansi             Force disable ANSI output

  CONFIGURED TASKS
    test           Run the test suite
    serve          Run the app in debug mode
    tunnel         Create an SSH tunnel to the production server
