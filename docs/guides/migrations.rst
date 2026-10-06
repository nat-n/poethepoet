Migration Guides
================

As a rule we avoid making breaking changes to poethepoet. However once in a while it is deemed necessary to make some minor breaking changes, which may impact a small minority of users, in order to make significant improvements overall. This guide details instances when this has occurred and gives advice on how to avoid or mitigate the impacts.

0.47.0
------

Boolean arg defaults must be boolean values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``default`` of an arg with :toml:`type = "boolean"` is now validated when the config is loaded. It must be a TOML boolean, one of the case-insensitive string literals ``"t"``, ``"true"``, ``"1"``, ``"f"``, ``"false"``, ``"0"``, or ``""``, or a templated string such as ``"${SOME_VAR}"`` that resolves to one of those literals. Any other string is rejected as a config error.

From 0.43.0 through 0.46.0 an arbitrary string default was accepted and exposed as the value of the variable when the flag was not provided, which made it possible to switch between two strings using the ``:-`` operator:

.. code-block:: toml

   # OLD: no longer supported
   [tool.poe.tasks.greet]
   cmd = "echo ${hello:-hello!}"
   args = [{ name = "hello", type = "boolean", default = "hi!" }]

As of 0.49.0 the same result is achieved with the ``true_string`` and ``false_string`` options, which set the string that a boolean arg is exposed as when its value is true or false respectively. The arg can then be referenced directly, without an expansion operator:

.. code-block:: toml

   # NEW: requires 0.49.0 or later
   [tool.poe.tasks.greet]
   cmd = 'echo "${hello}"'
   args = [{ name = "hello", type = "boolean", true_string = "hello!", false_string = "hi!" }]

Note that the ``:-`` and ``:+`` operators test the resulting string rather than the boolean value, so a nonempty ``false_string`` makes ``${hello:+...}`` expand even when the flag is false. See the :doc:`args guide<../guides/args_guide>` for details.

These options were not available in 0.47.x and 0.48.0, where the workaround is to make the arg a string type or move the logic into a shell or expr task.


0.46.0
------

This release rewrites the envfile parser to align with standard dotenv conventions and bash assignment syntax, and adds support for parameter expansion in env file values. This means that a ``$`` in env file values may now be interpreted differently, and two other edge-case behaviours changed.

Parameter expansion in unquoted and double-quoted values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Previously a ``$`` in an env file value was always kept literally. Now ``$VAR`` and ``${VAR}`` references in unquoted or double-quoted values are expanded, so for example ``PASSWORD=abc$def`` now sets ``PASSWORD`` to ``abc`` (if ``def`` is not set). To keep a literal ``$``, wrap the value in single quotes or escape the ``$`` with a backslash:

.. code-block:: bash

   PASSWORD='abc$def'
   PASSWORD=abc\$def

Whitespace in unquoted values is now preserved
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Previously, whitespace terminated an unquoted value, making it possible to write multiple assignments on a single line:

.. code-block:: bash

   # OLD: two assignments on one line (no longer supported)
   FOO=bar BAZ=qux

This is now parsed as a single assignment ``FOO`` with the value ``bar BAZ=qux``. Move such assignments to separate lines, or quote the value:

.. code-block:: bash

   # NEW: one assignment per line
   FOO=bar
   BAZ=qux

Semicolons are no longer assignment separators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Previously, ``;`` acted as an assignment separator (similar to shell statement separators), allowing constructs like:

.. code-block:: bash

   # OLD: two assignments separated by ; (no longer supported)
   FOO=bar;BAZ=qux

Semicolons are now treated as regular characters in unquoted values, so the above assigns ``bar;BAZ=qux`` to ``FOO``. Move assignments to separate lines:

.. code-block:: bash

   # NEW: one assignment per line
   FOO=bar
   BAZ=qux

If you have a value that contains a literal semicolon, it now works without escaping:

.. code-block:: bash

   # NEW: semicolons in values need no special treatment
   JDBC_URL=jdbc:postgresql://localhost:5432/mydb?options=first;second


0.44.0
------

This release adds support for recursive includes, which allows included files to themselves include other files. If a project includes config from another file which in turn includes config from other files then these transitive includes will now also be included in the main project by default. This new behavior can be disabled by setting ``recursive = false`` for a specific include, which will prevent any includes from that file from being followed. For more details see the :doc:`include guide<../guides/include_guide>`.

.. code-block:: toml

  [tool.poe]
   include = [{ path = "external/tasks.toml", recursive = false }]

When ``recursive`` is ``false``, the included file's own tasks and environment variables are still loaded, but any ``include`` entries within that file are not followed.


0.43.0
------

This release included a major refactor of how variables are managed which could unexpectedly change behavior in some situations.

Change in handling of boolean args
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To better support usage of boolean args in task logic, instead of mapping the arg value ``false`` to the string value ``False`` in the corresponding environment variable, it is instead mapped to *the environment variable being unset*, even if it was previously set on the environment. This allows more natural usage from most contexts, such as parameter expansion logic in cmd or shell tasks.

However some tasks or scripts may need to be updated if they previously checked for ``"False"`` specifically, or if they use ``set -u``.

Additionally if the variable was accessed from a python script via :python:`os.environ["flag"]` then this will break now. It is recommended to instead use :python:`"flag" in os.environ` or :python:`os.environ.get("flag")` to check if the flag is set to true.

As of 0.49.0 the string value for each case can be configured per arg with the ``true_string`` and ``false_string`` options. For example setting :toml:`false_string = ""` results in the variable being set to an empty string instead of unset when the flag is false, which avoids both of the problems described above. See the :doc:`args guide<../guides/args_guide>` for details.

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

Arg names are typically referenced within task content, and normally set as environment variables. However if an arg name is prefixed with an underscore to make it private, and there are no options explicitly configured for that arg, then any leading underscores will be stripped from the name when generating an option name from it. For example the arg name ``_flag`` will result in the cli option ``--flag``. The same applies to positional args: a private positional arg called ``_target`` will be displayed as ``target`` in help, while still being treated as a private variable inside the task.

Since this can cause collisions between options, there is now a config validation to prevent collisions between cli options.
