Migration Guides
================

As a rule we avoid making breaking changes to poethepoet. However once in a while it is deemed necessary to make some minor breaking changes, which may impact a small minority of users, in order to make significant improvements overall. This guide details instances when this has occurred and gives advice on how to avoid or mitigate the impacts.


0.43.0
------

This release included a major refactor of how variables are managed which could unexpectedly change behavior in some situations.

Change in handling of boolean args
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To better support usage of boolean args in task logic, instead of mapping the arg value ``false`` to the string value ``False`` in the corresponding environment variable, it is instead mapped to *the environment variable being unset*, even if it was previously set on the environment. This allows more natural usage from most contexts, such as parameter expansion logic in cmd or shell tasks.

However some tasks or scripts may need to be updated if they previously checked for ``"False"`` specifically, or if they use ``set -u``.

Additionally if the variable was accessed from a python script via :python:`os.environ["flag"]` then this will break now. It is recommended to instead use :python:`"flag" in os.environ` or :python:`os.environ.get("flag")` to check if the flag is set to true.

Note that as of this release you can reference the flag directly like a local python variable with a bool value in expr or script tasks, even if the arg was provided to a parent task, like a switch or sequence.

.. code-block:: toml

   [tool.poe.tasks.check-flag]
   expr = "flag and 'cli flag was set' or 'cli flag was not set'"
   args = [{ name = "flag", type = "boolean"}]


Introduction of private variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Any variable set within the project or task config (including referenced envfiles) that contains no uppercase letters and starts with an underscore, e.g. ``_private`` will not be exposed as an environment variable accessible to the task at runtime.

It seems unlikely that anyone would specifically need to pass variables like this to a task.

Using private variables is now encouraged as a best practice to avoid unintentionally setting environment variables on task subprocesses.

Arg names are typically referenced within task content, and normally set as environment variables. However if an arg name is prefixed with an underscore to make it private, and there are no options explicitly configured for that arg, then any leading underscores will be stripped from the name when generating an option name from it. For example the arg name ``_flag`` will result in the cli option ``--flag``.

Since this can cause collisions between options, there is now a config validation to prevent collisions between cli options.
