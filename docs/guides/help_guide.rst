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

.. raw:: html

    <div class="highlight-sh notranslate">
    <div class="highlight">
    <pre>$ poe --help
    <strong>Poe the Poet</strong> (version <span style="color:#56B6C2">0.43.0</span>)

    <strong>Usage:</strong>
      <span style="text-decoration:underline">poe</span> [global options] task [task arguments]

    <strong>Global options:</strong>
      <strong>-h, --help [TASK]</strong>     Show this help page and exit, optionally supply a
                            task.
      <strong>--version</strong>             Print the version and exit
      <strong>-v, --verbose</strong>         Increase output (repeatable)
      <strong>-q, --quiet</strong>           Decrease output (repeatable)
      <strong>-d, --dry-run</strong>         Print the task contents but don't actually run it
      <strong>-C, --directory PATH</strong>  Specify where to find the pyproject.toml
      <strong>-e, --executor EXECUTOR</strong>
                            Override the default task executor
      <strong>-X, --executor-opt KEY[=VALUE]</strong>
                            Set executor configuration for this run.
      <strong>--ansi</strong>                Force enable ANSI output
      <strong>--no-ansi</strong>             Force disable ANSI output

    <strong>Configured tasks:</strong>
      <span style="color:#56B6C2">test</span>           Run the test suite
      <span style="color:#56B6C2">serve</span>          Run the app in debug mode
      <span style="color:#56B6C2">tunnel</span>         Create an SSH tunnel to the production server
       <span style="color:#4B78CC">--prod_host</span>  Hostname of the production server [default: myapp.com]
    </pre>
    </div>
    </div>

Display help for a single task
------------------------------

Passing the ``--help`` option normally has the same effect as running poe with no arguments. However you can also supply the name of a task to display documentation for just that task.

.. raw:: html

    <div class="highlight-sh notranslate">
    <div class="highlight">
    <pre>$ poe --help tunnel

    <strong>Description:</strong>
      Create an SSH tunnel to the production server

    <strong>Usage:</strong>
      <span style="text-decoration:underline">poe</span> [global options] <span style="color:#56B6C2">tunnel</span> [named arguments] -- [free arguments]

    <strong>Named arguments:</strong>
      <span style="color:#4B78CC">--prod_host</span>    Hostname of the production server [default: myapp.com]
    </pre>
    </div>
    </div>

Grouping tasks
--------------

You can organize tasks into groups by defining them within group tables. This makes it easier to navigate large task lists and allows you to apply shared configuration (like an executor) to all tasks in a group.

.. code-block:: toml

  [tool.poe.tasks.test]
  help = "Run the tests"
  cmd = "pytest"

  [tool.poe.groups.server]
  heading = "Application Serving"
  executor = { type = "uv", group = "server" }  # Tasks in this group will run with uv's "server" dependency-group

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

When you run ``poe`` without specifying a task, ungrouped tasks appear first, followed by groups sorted alphabetically by group name:

.. raw:: html

    <div class="highlight-sh notranslate">
    <div class="highlight">
    <pre><strong>Configured tasks:</strong>
      <span style="color:#56B6C2">test</span>           Run the tests

    <span style="color:#98C379">Application Serving</span>
      <span style="color:#56B6C2">dev</span>            Run the app in debug mode
      <span style="color:#56B6C2">prod</span>           Run the app in production mode

    <span style="color:#98C379">Testing &amp; Quality</span>
      <span style="color:#56B6C2">unit</span>           Run the test suite
      <span style="color:#56B6C2">lint</span>           Run the linter
    </pre>
    </div>
    </div>


Group names must consist of only alphanumeric characters, dashes, or underscores.


Group options
~~~~~~~~~~~~~

- **heading**: A human-readable name for the group displayed in help output. If not specified, the group name is used.
- **executor**: Executor configuration that applies to all tasks in the group. Group executor config has higher precedence than project level, and lower precedence than task level config.
- **tasks**: A table of task definitions within the group.


Merging groups
~~~~~~~~~~~~~~

When an :ref:`included config file<Running tasks from another file>` defines a group with the same name as one in the main project config, the tasks from both are merged under a single heading. Only group config (e.g. heading and executor) from the config file with the highest precedence is preserved when merging groups.
