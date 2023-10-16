``switch`` tasks
================

Much like a switch statement in many programming languages, a switch task consists of a control task and a array of tasks to switch between. The control task is run first, and its output is captured and matched against the case option of each of the items in the switch array to determine which one to run.

This can be used to define a task that runs a different subtask depending on which platform it is running on like so:

.. code-block:: toml

  [tool.poe.tasks.build]
  control.expr = "sys.platform"

    [[tool.poe.tasks.build.switch]]
    case = "win32"
    cmd  = "windows_build"

    [[tool.poe.tasks.build.switch]]
    cmd  = "posix_build"

In the above example the control task is an :doc:`expression <expr>` that checks the value of ``sys.platform``, and if running on windows it'll execute :toml:`windows_build`, otherwise it'll fall back to the default case (i.e. the switch item with no case option defined) and execute :toml:`posix_build`.


Available task options
----------------------

``switch`` tasks support all of the :doc:`standard task options <../options>` with the exception of ``use_exec``.

The following options are also accepted:

**control** : ``str`` | ``dict``
  A **required** inline definition for a task to be executed to get the value that will determine which case task to run.

**default** : ``Literal["pass"]`` | ``Literal["fail"]`` :ref:`📖<Don't fail if there's no match>`
  Setting ``default =  "pass"`` will make the task succeed even if no case was matched to the value and there was no default case.


Multiple values per case
------------------------

It is also possible to define multiple values for a single case option by providing a
array of values like so:

.. code-block:: toml

    [[tool.poe.tasks.build.switch]]
    case = ["linux", "darwin"]
    cmd  = "build"

Don't fail if there's no match
------------------------------

If all tasks in the switch array include a case value, but none of them match the result
of the control task then by default the switch task will fail. You can instead configure
the switch task to pass and simply do nothing by providing the 'default' option like so:

.. code-block:: toml

  [tool.poe.tasks.build-on-windows]
  control.expr = "sys.platform"
  default = "pass"

    [[tool.poe.tasks.build-on-windows.switch]]
    case = "win32"
    cmd  = "build"

Switching on an environment variable
------------------------------------

Using an :doc:`expr <expr>` task makes it convenient to run a different task depending on the value of an environment variable as in the following example:

.. code-block:: toml

  [tool.poe.tasks.check_number]
  control.expr = "int(${BEST_NUMBER}) % 2"

    [[tool.poe.tasks.check_number.switch]]
    case = "0"
    expr = "f'{${BEST_NUMBER}} is even')"

    [[tool.poe.tasks.check_number.switch]]
    case = "1"
    expr = "f'{${BEST_NUMBER}} is odd'"

Using this task will look like the following:

.. code-block:: sh

  $ BEST_NUMBER=12 poe check_number
  Poe <= int(${BEST_NUMBER}) % 2
  Poe => f'{${BEST_NUMBER}} is even')
  12 is even

  $ BEST_NUMBER=17 poe check_number
  Poe <= int(${BEST_NUMBER}) % 2
  Poe => f'{${BEST_NUMBER}} is odd'
  17 is odd


Switching on a named argument
-----------------------------

You can also run a different task depending on the value of a named argument as in the following example.

.. code-block:: toml

  [tool.poe.tasks.icecream]
  control.expr = "flavor"
  args = ["flavor"]

    [[tool.poe.tasks.icecream.switch]]
    case = "chocolate"
    cmd  = "make_chocolate_icecream"

    [[tool.poe.tasks.icecream.switch]]
    case = "strawberry"
    cmd  = "make_strawberry_icecream"

    [[tool.poe.tasks.icecream.switch]]
    cmd  = "make_vanilla_icecream"

So running this task would look like:

.. code-block:: sh

  $ poe icecream --flavor chocolate
  Poe <= flavor
  Poe => make_chocolate_icecream
  ...
