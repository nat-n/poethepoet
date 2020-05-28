Load tasks from another file
============================

There are some scenarios where one might wish to define tasks outside of pyproject.toml,
or to collect tasks from multiple projects into one. For example, if you want to share
tasks between projects via git modules, generate tasks definitions dynamically, organise
your code in a monorepo, or simply have a lot of tasks and don't want the pyproject.toml
to get too large. This can be achieved by creating a toml or json including the same
structure for tasks as used in pyproject.toml

For example:

.. code-block:: toml

  # acme_common/shared_tasks.toml
  [tool.poe.tasks.build-image]
  cmd = "docker build"


.. code-block:: toml

  [tool.poe]
  # this references a file from a git submodule
  include = "modules/acme_common/shared_tasks.toml"

Imported files may also specify environment variables via
:code:`tool.poe.envfile` or entries for :code:`tool.poe.env`.

It's also possible to include tasks from multiple files by providing a list like
so:

.. code-block:: toml

  [tool.poe]
  include = ["modules/acme_common/shared_tasks.toml", "generated_tasks.json"]

Files are loaded in the order specified. If an item already exists then the included
value it ignored.

If an included task file itself includes other files, these second order includes are
not inherited, so circular includes don't cause any problems.

When including files from another location, you can also specify that tasks from that
other file should be run from within a specific directory. For example with the
following configuration, when tasks imported from my_subproject are run
from the root, the task will actually execute as if it had been run from the
my_subproject subdirectory.

.. code-block:: toml

  [[tool.poe.include]]
  path = "my_subproject/pyproject.toml"
  cwd  = "my_subproject"

The cwd option still has the limitation that it cannot be used to specify a directory
outside of parent directory of the pyproject.toml file that poe is running with.

If a referenced file is missing then poe ignores it without error, though
failure to read the contents will result in failure.


Configuring the plugin
----------------------

By default the poetry plugin will register *poe* as a command prefix so tasks can be
invoked like:

.. code-block:: sh

  poetry poe [task_name] [task_args]

And the poe documentation can be viewed via:

.. code-block:: bash

  poetry poe

It is also possible to modify this behavoir, to either have a different command prefix
or none at all by setting the :toml:`poetry_command` global option in your
pyproject.toml like so:

.. code-block:: toml

  [tool.poe]
  poetry_command = ""

In this case poe tasks will be registered as top level commands on poetry and can be
invoked simply as:

.. code-block:: sh

  poetry [task_name]

.. warning::
    Whatever :toml:`tool.poe.poetry_command` is set to must not already exist as a
    poetry command!

    Additionally if setting it to the emtpy string then care must be taken to avoid
    defining any poe tasks that conflict with any other built in or plugin provided
    poetry command.

Hooking into poetry commands
----------------------------

It is also possible to configure a task to be run before or after a specific poetry
command by declaring the poetry_hooks global option like so:

.. code-block:: toml

  [tool.poe.poetry_hooks]
  pre_build  = "prep-assets --verbosity=5"
  post_build = "archive-build"

  [tool.poe.tasks.prep-assets]
  script = "scripts:prepare_assets"
  help   = "Optimise static assets for inclusion in the build"

  [tool.poe.tasks.archive-build]
  script = "scripts:archive_build"
  help   = "Upload the latest build version to archive server"

In this example the :code:`prep-assets` task will be run as the first step in calling
:bash:`poetry build` with an argument passed as if the task were being called via the
poe CLI. We've also configured the :code:`archive-build` task to be run after every
successful build.

If a task fails when running as a hook, then the poetry command will exit with an error.
If it is a *pre* hook then this will cause the actual poetry command not to execute.
This behaviour may be useful for running checks before :bash:`poetry publish`

Hooks can be disabled for a single invocation by passing the :bash:`--no-plugins` option
to poetry.

Namespaced commands like :bash:`poetry env info` can be specified with underscores like so:

.. code-block:: toml

  [tool.poe.poetry_hooks]
  post_env_info = "info"
