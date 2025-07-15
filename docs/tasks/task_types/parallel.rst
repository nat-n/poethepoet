``parallel`` tasks
==================

A **Parallel task** is defined by an array of other tasks to be run concurrently.

The array items can be sub-tables that declare inline tasks, or strings :doc:`referencing<ref>` to other tasks.

.. code-block:: toml

  [tool.poe.tasks]
  parallel = ["mypy", "pylint"]

By default the contents of the array are interpreted as references to other tasks (actually an inline :doc:`ref<ref>` task). However, this behaviour can be altered by setting the :toml:`default_item_type` option locally on the parallel task.

The output of each parallel task is shown as it arrives. The :toml:`capture_stdout` option can be used on to redirect the output of each included task into a dedicated file.


Available task options
----------------------

``parallel`` tasks support all of the :doc:`standard task options <../options>` with the exception of ``use_exec`` and ``capture_stdout``.

The following options are also accepted:

**ignore_fail** : ``bool`` | ``str`` :ref:`📖<Continue on task failure>`
  If true then the failure (or non-zero return value) of one task in the parallel group does not abort the execution.

**default_item_type** : ``str`` :ref:`📖<Changing the default item type>`
  Change the task type that is applied to string array items in this parallel group.


Continue on task failure
------------------------

A failure (non-zero result) will result in an error being raised, unless the :toml:`ignore_fail` option is set on the task to
:toml:`true` or :toml:`"return_zero"` like so:

.. code-block:: toml

  [tool.poe.tasks.lint]
  parallel = ["mypy", "pylint", "flake8"]
  ignore_fail = "return_zero"


Changing the default item type
------------------------------

If you want strings in the array to be interpreted as a task type other than :doc:`ref<ref>` you may specify then :toml:`default_item_type` option like so:

.. code-block:: toml

  parallel = [
    "linters:run_mypy(all=True)",
    "linters:run_pylint",
    "linters:run_flake8",
  ]
  default_item_type = "script"


Using parallel tasks within sequences
-------------------------------------

Parallel tasks can be used within sequence tasks to run a group of tasks in parallel as part of a larger sequence. This is done by referencing a parallel task in a sequence:

.. code-block:: toml

  [tool.poe.tasks.format]
  parallel = ["format_project1", "format_project2"]

  [tool.poe.tasks.lint]
  parallel = ["lint_project1", "lint_project2"]

  [tool.poe.tasks.fix]
  sequence = ["format", "lint"]

In this example, all formatting will run in parallel and all linting will run in parallel but no linting will start before the formatting finished.
