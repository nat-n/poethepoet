Loading tasks from another file
===============================

There are some scenarios where one might wish to define tasks outside of pyproject.toml, or to collect tasks from multiple projects into one. For example, if you want to share tasks between projects via git modules, generate tasks definitions dynamically, organise your code in a monorepo, or simply have a lot of tasks and don't want the pyproject.toml to get too large. This can be achieved by creating a toml or json file including the same structure for tasks as used in pyproject.toml

For example:

.. code-block:: toml

  # pyproject.toml

  [tool.poe]
  include = "modules/acme_common/shared_tasks.toml" # include tasks from a git submodule

.. code-block:: toml

  # acme_common/shared_tasks.toml

  [tool.poe.tasks.build-image]
  cmd = "docker build"

Imported files may also specify environment variables via
``tool.poe.envfile`` or entries for ``tool.poe.env``.

.. tip::

  If a referenced file is missing then poe ignores it without error, though failure to read the contents will result in failure.


Including multiple files
------------------------

It's also possible to include tasks from multiple files by providing a list like so:

.. code-block:: toml

  [tool.poe]
  include = ["modules/acme_common/shared_tasks.toml", "generated_tasks.json"]

Files are loaded in the order specified. If an item already exists then the included value is ignored.

If an included task file itself includes other files, these second order includes are **not inherited**, so circular includes are not a concern.


Setting a working directory for included tasks
----------------------------------------------

When including files from another location, you can also specify that tasks from that other file should be run from within a specific directory. For example with the following configuration, when tasks imported from my_subproject are run from the root, the task will actually execute as if it had been run from the *my_subproject* subdirectory.

.. code-block:: toml

  [[tool.poe.include]]
  path = "my_subproject/pyproject.toml"
  cwd  = "my_subproject"

The cwd option still has the limitation that it cannot be used to specify a directory outside of parent directory of the pyproject.toml file that poe is running with.
