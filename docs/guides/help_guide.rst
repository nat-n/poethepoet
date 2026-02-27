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

Grouping tasks
--------------

You can organize tasks into groups by defining them within group tables. This makes it easier to navigate large task lists and allows you to apply shared configuration (like an executor) to all tasks in a group.

.. code-block:: toml

  [tool.poe.groups.server]
  heading = "Application Serving"
  executor = { type = "uv", group = "server" }  # Applies to all tasks in this group

  [tool.poe.groups.server.tasks.dev]
  help = "Run the app in debug mode"
  cmd  = "uvicorn my_app:app --reload"

  [tool.poe.groups.server.tasks.prod]
  help = "Run the app in production mode"
  cmd  = "uvicorn my_app:app"

  [tool.poe.groups.testing]
  heading = "Testing & Quality"

  [tool.poe.groups.testing.tasks.test]
  help = "Run the test suite"
  cmd  = "pytest --cov=my_app"

  [tool.poe.groups.testing.tasks.lint]
  help = "Run the linter"
  cmd  = "ruff check ."

When you run ``poe`` without specifying a task, tasks will be grouped by their group heading in the help output:

.. code-block:: text

  $ poe
  Poe the Poet (version 0.40.0)

  Usage:
    poe [global options] task [task arguments]

  Configured tasks:

    Application Serving
      dev   Run the app in debug mode
      prod  Run the app in production mode

    Testing & Quality
      test  Run the test suite
      lint  Run the linter

**Group Options:**

- **heading**: A human-readable name for the group displayed in help output. If not specified, the group name is used.
- **executor**: Executor configuration that applies to all tasks in the group (unless a task overrides it).
- **tasks**: A table of task definitions within the group.

**Merging Groups:**

Groups from different config files with the same name will be merged together. Tasks from later config files are added to the group.
