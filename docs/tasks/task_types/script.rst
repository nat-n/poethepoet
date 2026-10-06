``script`` tasks
================

**Script tasks** consist of a reference to a python callable to import and execute, and optionally values or expressions to pass as arguments, for example:

.. code-block:: toml

  [tool.poe.tasks]
  fetch-assets.script = "my_pkg.assets:fetch"
  fetch-images.script = "my_pkg.assets:fetch(only='images', log=environ['LOG_PATH'])"

As in the second example, it is possible to hard code literal arguments to the target callable. In fact a subset of Python syntax, operators, and globals can be used inline to define the arguments to the function using normal Python syntax, including environ (from the os package) to access environment variables that are available to the task.

If extra arguments are passed to task on the command line (and no CLI args are declared), then they will be available within the called Python function via :python:`sys.argv`. If :doc:`args <../options>` are configured for the task then they will be available as Python variables.

If the target Python function is an async function, or otherwise returns an awaitable (such as a coroutine), then the result will be awaited via :python:`asyncio.run`.


Available task options
----------------------

``script`` tasks support all of the :doc:`standard task options <../options>`.

The following options are also accepted:

**print_result** : ``bool`` :ref:`📖<Output the return value>`
  If true then the return value of the python callable will be output to stdout, unless it is ``None``.

**ignore_fail** : ``bool`` | ``list[int]``  :ref:`📖<Ignore task failure>`
  Return exit code 0 even if the task fails, or specify a list of task exit codes to ignore.


Update the PYTHONPATH to access scripts
----------------------------------------

The module containing the function for the ``script`` task to call must be importable by the task subprocess running with whatever environment the PoeExecutor uses (e.g. the uv or poetry managed venv).

This is fine if functions for poe tasks are defined alongside other source in a `./src/tasks` directory for instance, but sometimes it's convenient to place scripts for a project somewhere like ``./scripts/my_script.py``, which will not normally be on the python path. We can still call functions from the ``my_script`` module by setting the standard ``PYTHONPATH`` environment variable on the task like so:

.. code-block:: toml

  [tool.poe.tasks.my-task]
  script = "my_script:my_function"
  env.PYTHONPATH = "${POE_ROOT}/scripts"

Referencing ``POE_ROOT`` ensures the path is absolute, since a relative ``PYTHONPATH`` would be resolved relative to the working directory of the task, which may differ from the project root if the :ref:`cwd<Running a task with a specific working directory>` option is set.

.. note::

  Modules located directly in the project root are normally importable because the task's working directory is on the python path, so setting the ``cwd`` option on a script task may break imports of such modules. In this case you can also set :toml:`env.PYTHONPATH = "${POE_ROOT}"`.


Run a ``__main__`` module as a script task
------------------------------------------

A script task may reference a package instead of a specific callable, in which case the package's ``__main__.py`` module will be executed as a script task, or the module itself if it's not a package (the usual behavior from ``python -m``). This is useful for running a package or module that has been designed to be run as a script.

For example, the following task will run the ``http.server`` module as a script task, which will start a simple HTTP server. Any command line arguments passed to the task will be forwarded to the script.

.. code-block:: toml

  [tool.poe.tasks.serve]
  script = "http.server"
  args = [
    { name = "port", positional = true, default = "8000" },
    { name = "bind", options = ["-b", "--bind"], default = "127.0.0.1" },
  ]

When :doc:`args <../options>` are declared on the task, the parsed values (with defaults applied) are re-emitted onto the module's :python:`sys.argv`. CLI tokens that aren't matched by a declared arg result in an error, but any tokens that follow :sh:`--` are forwarded to the module verbatim. If no args are declared then all CLI tokens are forwarded to the module verbatim.

Like the callable form, the module form also implicitly adds :sh:`<project_root>/src` to the subprocess :sh:`PYTHONPATH` so that modules placed in a ``src/`` directory at the project root are importable without extra configuration.


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

whereas the same behaviour can be reliably achieved like so:

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

However it is possible to configure poe to delegate respecting this dry run flag to an invoked script task, by passing it the ``_dry_run`` variable. When this variable is passed as an argument to the Python function called within a script task then poe will always call the task, and delegate responsibility to the script for making sure that no side effects occur when run in dry-run mode.


Task arguments
--------------

As with other task types, script tasks support configuring named arguments via the ``args`` option. Arguments are accessible in the referenced Python function in three ways:

- As **Python variables** that can be referenced directly in the function call expression. Values retain their configured type — booleans are ``True``/``False``, integers are ``int``, multiple args are ``list``, etc.
- Via **sys.argv** which is populated with the full invocation including any extra arguments.
- As **keyword arguments** when the script reference doesn't include explicit parentheses — in this case all args declared on the task itself are passed as kwargs. Args inherited from a parent task (e.g. a sequence or ref task) are not passed as kwargs, though they can still be referenced by name when the parentheses are included.

See :ref:`Arguments for script tasks` for more details and examples.


Accessing free arguments via ``_extra_args``
--------------------------------------------

Free arguments (all arguments if the task declares no named args, or otherwise arguments passed after :sh:`--`) are available inside script tasks as the ``_extra_args`` variable — a ``list[str]``, which is empty if no free arguments were passed — in addition to the ``$POE_EXTRA_ARGS`` environment variable.

See the :ref:`forwarding-free-arguments-via-poe-extra-args` section of the args guide for details and examples.
