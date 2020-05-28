"sequence" tasks
================

Sequence tasks are defined as a array of other tasks to be run one after the other.

By default the contents of the array are interpreted as references to other tasks
(actually a ref task type), though this behaviour can be altered by setting the global
:toml:`default_array_item_task_type` option to the name of another task type such as
*cmd*, or by setting the :toml:`default_item_type` option locally on the sequence task.

Sequence task with references
-----------------------------

.. code-block:: toml

  [tool.poe.tasks]

  test = "pytest --cov=src"
  build = "poetry build"
  _publish = "poetry publish"
  release = ["test", "build", "_publish"]

Note that tasks with names prefixed with :code:`_` are not included in the
documentation or directly executable, but can be useful for cases where a task is only
needed for referencing from another task.

Sequence task with inline tasks expressed via inline tables
-----------------------------------------------------------

.. code-block:: toml

  [tool.poe.tasks]

  release = [
    { cmd = "pytest --cov=src" },
    { script = "devtasks:build" },
    { ref = "_publish" }
  ]

Sequence task with inline tasks expressed via an array of tables
----------------------------------------------------------------

.. code-block:: toml

  [tool.poe.tasks]

    [[tool.poe.tasks.release]]
    cmd = "pytest --cov=src"

    [[tool.poe.tasks.release]]
    script = "devtasks:build"

    [[tool.poe.tasks.release]]
    ref = "_publish"

Sequence task with inline script subtasks using :code:`default_item_type`
-------------------------------------------------------------------------

.. code-block:: toml

  release.sequence = [
    "devtasks:run_tests(all=True)",
    "devtasks:build",
    "devtasks:publish",
  ]
  release.default_item_type = "script"

A failure (non-zero result) will result in the rest of the tasks in the sequence not
being executed, unless the :toml:`ignore_fail` option is set on the task to
:toml:`true` or :toml:`"return_zero"` like so:

.. code-block:: toml

  [tool.poe.tasks]
  attempts.sequence = ["task1", "task2", "task3"]
  attempts.ignore_fail = "return_zero"

If you want to run all the subtasks in the sequence but return non-zero result in the
end of the sequence if any of the subtasks have failed you can set :toml:`ignore_fail`
option to the :toml:`return_non_zero` value like so:

.. code-block:: toml

  [tool.poe.tasks]
  attempts.sequence = ["task1", "task2", "task3"]
  attempts.ignore_fail = "return_non_zero"


