``script`` tasks
================

**Script tasks** consist of a reference to a python callable to import and execute, and optionally values or expressions to pass as arguments, for example:

.. code-block:: toml

  [tool.poe.tasks]
  fetch-assets.script = "my_pkg.assets:fetch"
  fetch-images.script = "my_pkg.assets:fetch(only='images', log=environ['LOG_PATH'])"

As in the second example, is it possible to hard code literal arguments to the target callable. In fact a subset of python syntax, operators, and globals can be used inline to define the arguments to the function using normal python syntax, including environ (from the os package) to access environment variables that are available to the task.

If extra arguments are passed to task on the command line (and no CLI args are declared), then they will be available within the called python function via :python:`sys.argv`. If :doc:`args <../options>` are configured for the task then they will be available as python variables.

If the target python function is an async function then it will be executed with :python:`asyncio.run`.


Available task options
----------------------

``script`` tasks support all of the :doc:`standard task options <../options>`.

The following options are also accepted:

**print_result** : ``bool`` :ref:`📖<Output the return value>`
  If true then the return value of the python callable will be output to stdout, unless it is ``None``.


Output the return value
-----------------------

Script tasks can be configured to output the return value of the python callable using the :toml:`print_result` option.

.. code-block:: toml

  [tool.poe.tasks.create-secret]
  script = "django.core.management.utils:get_random_secret_key()"
  print_result = true

Given the above configuration running the following command would output just the
generated key.

.. code-block:: bash

  poe -q create-secret

Note that if the return value is None then the :toml:`print_result` option has no
effect.


Calling standard library functions
----------------------------------

Any python callable accessible via the python path can be referenced, including the
standard library. This can be useful for ensuring that tasks work across platforms.

For example, the following task will not always work on windows:

.. code-block:: toml

  [tool.poe.tasks.build]
  cmd = "mkdir -p build/assets"

whereas the same behaviour can can be reliably achieved like so:

.. code-block:: toml

  [tool.poe.tasks.build]
  script = "os:makedirs('build/assets', exist_ok=True)"


Poe scripts library
-------------------

Poe the Poet includes the ``poethepoet.scripts`` package including the following functions as convenient cross-platform implementations of common task capabilities.
These functions can be referenced from script tasks if ``poethepoet`` is available in the project virtual environment.

.. autofunction:: poethepoet.scripts.rm


Delegating dry-run behavior to a script
---------------------------------------

Normally if the ``--dry-run`` global option is passed to the CLI then poe will go through the motions of running the given task, including logging to stdout, without actually running the task.

However it is possible to configure poe to delegate respecting this dry run flag to an invoked script task, by passing it the ``_dry_run`` variable. When this variable is passed as an argument to the python function called within a script task then poe will always call the task, and delegate responsibility to the script for making sure that no side effects occur when run in dry-run mode.
