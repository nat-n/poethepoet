``matrix`` tasks
================

A **matrix task** runs an inline task definition once for each combination of matrix
variable values, much like the environment matrix of tox. This makes it possible to
run the same task against multiple configurations, such as several Python versions,
without duplicating the task definition.

.. code-block:: toml

  [tool.poe.tasks.test]
  matrix = { "py" = ["3.11", "3.12", "3.13"] }
  task.cmd = "pytest"
  task.executor = { type = "uv", isolated = true, python = "${py}" }

Each variable of the matrix is set in the environment of the subtask for that
combination, so ``${py}`` above resolves to ``3.11``, then ``3.12``, then ``3.13``.
Combinations run one after another, and the matrix task is aborted if any of them
fails, just like a :doc:`sequence<sequence>` task.

The matrix option maps each variable name to the list of values it takes. Variable
names must be valid environment variable names, values must be unique within their
variable, and values are used in the generated task names described below, so they may
only contain word characters, colon, plus, dash, or dot separated groups.


Running a single combination
----------------------------

Every combination also gets a generated task name, so a single combination can be run
on its own without being declared separately. The generated name is the task name
followed by each variable and its value, joined with dashes:

.. code-block:: sh

  $ poe test-py3.12
  Poe => pytest
  ...

With multiple variables, such as ``matrix = { "py" = ["3.11"], "arch" = ["x86"] }``,
the generated name includes each of them, for example ``test-py3.11-archx86``.
Combinations can also be referenced from other tasks, for example as items of a
:doc:`sequence<sequence>` task or in the ``deps`` option of another task.

.. note::

  Tasks with names starting with an underscore are hidden from the documentation and
  cannot be run directly, and this applies to the combinations they generate too.


Selecting a subset of the matrix
--------------------------------

A matrix variable that is already set by one of the task's own args is not expanded,
so the matrix can be narrowed to a subset of its values:

.. code-block:: toml

  [tool.poe.tasks.test]
  matrix = { "py" = ["3.11", "3.12", "3.13"] }
  args = [{ name = "py", options = ["--python-versions"], multiple = true }]
  task.cmd = "pytest"
  task.executor = { type = "uv", isolated = true, python = "${py}" }

.. code-block:: sh

  $ poe test --python-versions 3.12 3.13
  ...

.. warning::

  An argument that shares its name with a matrix variable must not declare a default
  value, since the default would permanently narrow the matrix to a single
  combination.


Forwarding free arguments via ``$POE_EXTRA_ARGS``
-------------------------------------------------

Free arguments passed to a matrix task are available as ``$POE_EXTRA_ARGS`` and are
inherited by each subtask, so they can be forwarded to whichever command the subtask
runs.

See the :ref:`forwarding-free-arguments-via-poe-extra-args` section of the args guide
for details and examples.


Available task options
----------------------

``matrix`` tasks support all of the :doc:`standard task options <../options>` with the
exception of ``capture_stdout``.

The following options are also accepted:

**task** : ``str`` | ``dict``
  A **required** inline definition for the task to run for each combination of matrix
  variable values. As for subtasks of a sequence or parallel task, it may not declare
  the ``args``, ``deps``, ``uses``, or ``uses_env`` options. To run another named task
  for each combination, reference it with an inline :doc:`ref<ref>` task.
