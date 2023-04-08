Documenting tasks
-----------------

You can add help text to your tasks by adding a :code:`help` key to your task definition, like so:

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

This will allow you to run :code:`poe --help` and see the help text for your tasks.

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

You can find a more complex example of tasks in `this repo's pyproject.toml <https://github.com/nat-n/poethepoet/blob/main/pyproject.toml#L43>`_ file.
