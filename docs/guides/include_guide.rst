Loading tasks from another file
===============================

There are some scenarios where one might wish to define tasks outside of pyproject.toml, or to collect tasks from multiple projects into one. For example, if you want to share tasks between projects via git modules, generate tasks definitions dynamically, organize your code in a monorepo, or simply have a lot of tasks and don't want the pyproject.toml to get too large. This can be achieved by creating a toml, yaml, or json file including the same structure for tasks as used in pyproject.toml

.. tip::

  Imported toml, yaml, or json files are not required to namespace config under ``tool.poe``. However if config exists under this structure then it will be used.

For example:

.. code-block:: toml
  :caption: ./pyproject.toml

  [tool.poe]
  include = "modules/acme_common/shared_tasks.toml" # include tasks from a git submodule

.. code-block:: toml
  :caption: ./modules/acme_common/shared_tasks.toml

  [tool.poe.tasks.build-image]
  cmd = "docker build"

Imported files may also specify environment variables via
``tool.poe.envfile`` or entries for ``tool.poe.env``. Note that these are merged into the global environment, and so apply to *all* tasks, including tasks defined in the main config file or in other included files. In case of conflicts, values from later includes override those from earlier includes (unlike tasks, where the first definition wins), and values set via ``env`` or ``envfile`` in the main config file override values from all included files.

.. warning::

  If a referenced file is missing then poe ignores it and just prints a warning, though failure to read the contents will result in failure.

Disabling recursion
-------------------

By default, includes are followed recursively. You can disable this for a specific include by setting ``recursive = false``:

.. code-block:: toml

  [[tool.poe.include]]
  path = "external/tasks.toml"
  recursive = false

When ``recursive`` is ``false``, the included file's own tasks and environment variables are still loaded, but any ``include`` entries within that file are not followed.


Including tasks from a python package
-------------------------------------

You can also include tasks from a python function originating either within the current project or from a dependency. This makes it much easier to share tasks across projects by distributing them as a python package, or to dynamically generate tasks depending on the context.

For more details see the :doc:`include_script<../guides/packaged_tasks>` global option.

The ``include_script`` option is ignored in included files due to the complexity of coordinating executors (for loading the scripts) across config files. So ``include_script`` can only be used in the main pyproject.toml file.


Including multiple files
------------------------

It's also possible to include tasks from multiple files by providing a list like so:

.. code-block:: toml

  [tool.poe]
  include = ["modules/acme_common/shared_tasks.toml", "generated_tasks.json"]

Files are loaded in the order specified. If an item already exists then the included value is ignored.

Included files can themselves include other files. These are loaded depth first in the order specified, each one after the file that includes it, so if the same task name is defined in multiple files then the including file's task wins (and tasks from the main config file always win). The include paths within an included file are resolved relative to the directory containing that file.


Setting a working directory for included tasks
----------------------------------------------

When including files from another location, you can also specify that tasks from that other file should be run from within a specific directory. For example with the following configuration, when tasks imported from *my_subproject* are run from the root, the task will actually execute as if it had been run from the *my_subproject* subdirectory.

.. code-block:: toml

  [[tool.poe.include]]
  path = "my_subproject/pyproject.toml"
  cwd  = "my_subproject"

This also applies when an included task is invoked by another task (e.g. via ``deps``, ``uses``, a ``ref`` task, or a ``sequence``), unless the referencing task sets its own ``cwd`` option, in which case that is used instead.

The directory indicated by the ``cwd`` option will also be used as the base directory for global or task level ``envfile`` imports for tasks defined within an included file.

Tasks and config in an included file can access the ``cwd`` value via the ``POE_CONF_DIR`` environment variable. When no ``cwd`` is set on the include then ``POE_CONF_DIR`` refers to the parent directory of the config file where a task is defined.

You can still specify that an envfile referenced within an included file should be imported relative to the main project root, using the ``POE_ROOT`` environment variable like so:

.. code-block:: toml

  [tool.poe]
  envfile = "${POE_ROOT}/.env"


Including files relative to the git repo
----------------------------------------

Normally include paths in the main config file are resolved relative to the project root (that is the parent directory of the pyproject.toml). However when working with a monorepo it can also be useful to specify the file to include relative to the root of the git repository, which can be done by referencing the ``POE_GIT_DIR`` or ``POE_GIT_ROOT`` variables like so:

.. code-block:: toml

  [tool.poe]
  include = "${POE_GIT_DIR}/tasks.toml"

See the documentation on :ref:`Special variables<Special variables>` for a full explanation of how these variables work.
