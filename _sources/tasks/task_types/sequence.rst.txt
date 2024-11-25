``sequence`` tasks
==================

A **Sequence task** is defined by an array of other tasks to be run one after the other.

The array items can be sub-tables that declare inline tasks, or strings :doc:`referencing<ref>` to other tasks.

.. code-block:: toml

  [tool.poe.tasks]

  test = "pytest --cov=src"
  build = "poetry build"
  _publish = "poetry publish"
  release = ["test", "build", "_publish"]

.. important::

   Task with names prefixed with an underscore ``_`` are excluded from documentation and cannot be run directly from the command line, but can be useful for cases where a task is only needed for referencing from another task.

By default the contents of the array are interpreted as references to other tasks (actually an inline :doc:`ref<ref>` task). However, this behaviour can be altered by setting the global :toml:`default_array_item_task_type` option to the name of another task type such as ``"cmd"``, or by setting the :toml:`default_item_type` option locally on the sequence task.


Available task options
----------------------

``sequence`` tasks support all of the :doc:`standard task options <../options>` with the exception of ``use_exec`` and ``capture_stdout``.

The following options are also accepted:

**ignore_fail** : ``bool`` | ``str`` :ref:`📖<Continue sequence on task failure>`
  If true then the failure (or non-zero return value) of one task in the sequence does not abort the sequence.

**default_item_type** : ``str`` :ref:`📖<Changing the default item type>`
  Change the task type that is applied to string array items in this sequence.


Continue sequence on task failure
---------------------------------

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

.. |array_of_tables_link| raw:: html

   <a href="https://toml.io/en/v1.0.0#array-of-tables" target="_blank">array of tables</a>


Changing the default item type
------------------------------

If you want strings in the array to be interpreted as a task type other than :doc:`ref<ref>` you may specify then :toml:`default_item_type` option like so:

.. code-block:: toml

  release.sequence = [
    "devtasks:run_tests(all=True)",
    "devtasks:build",
    "devtasks:publish",
  ]
  release.default_item_type = "script"


Sequence task as an array of tables
-----------------------------------

When declaring more complex sequences the following syntax is often preferred.

.. code-block:: toml

  [tool.poe.tasks]

    [[tool.poe.tasks.release.sequence]]
    cmd = "pytest --cov=src"

    [[tool.poe.tasks.release.sequence]]
    script = "devtasks:build"

    [[tool.poe.tasks.release.sequence]]
    ref = "_publish"

.. important::

  Double square brackets in toml specify an |array_of_tables_link|.

.. hint::

  Using sequences in this way is sometimes a good alternative to a :doc:`shell <shell>` task, which may be less portable.

.. warning::

  Note that tasks defined inline within a sequence may not include some options that would otherwise be available to them, for example ``help`` and ``args`` are forbidden because they don't make sense in this context.


Sequence task as an array of inline tables
------------------------------------------

In some simpler cases a more succinct syntax may be preferred, missing strings (for ref tasks) and inline tables for other task types like so:

.. code-block:: toml

  [tool.poe.tasks]

  release = [
    { cmd = "pytest --cov=src" },
    { script = "devtasks:build" },
    "_publish"
  ]
