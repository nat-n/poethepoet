"script" tasks
==============

**Script tasks** consist of a reference to a python callable to import and execute, and optionally values or expressions to pass as arguments, for example:

.. code-block:: toml

  [tool.poe.tasks]
  fetch-assets = { "script" = "my_package.assets:fetch" }
  fetch-images = { "script" = "my_package.assets:fetch(only='images', log=environ['LOG_PATH'])" }

As in the second example, is it possible to hard code literal arguments to the target
callable. In fact a subset of python syntax, operators, and globals can be used inline
to define the arguments to the function using normal python syntax, including environ
(from the os package) to access environment variables that are available to the task.

If extra arguments are passed to task on the command line (and no CLI args are
declared), then they will be available within the called python function via
:python:`sys.argv`.

If the target python function is an async function then it will be exectued with :python:`asyncio.run`.

Calling standard library functions
----------------------------------

Any python callable accessible via the python path can be referenced, including the
standard library. This can be useful for ensuring that tasks work across platforms.

For example, the following task will not always work on windows:

.. code-block:: toml

  [[tool.poe.tasks.build]]
  cmd = "mkdir -p build/assets"

whereas the same behaviour can can be reliably achieved like so:

.. code-block:: toml

  [[tool.poe.tasks.build]]
  script = "os:makedirs('build/assets', exist_ok=True)"

Output the return value from the python callable
------------------------------------------------

Script tasks can be configured to output the return value of a callable using the
:toml:`print_result` option like so:

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

