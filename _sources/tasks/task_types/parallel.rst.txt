``parallel`` tasks
==================

A **Parallel task** is defined by an array of other tasks to be run concurrently.

.. code-block:: toml

  [tool.poe.tasks]
  parallel = ["mypy", "pylint"]

By default the contents of the array are interpreted as references to other tasks (actually an inline :doc:`ref<ref>` task). However, this behaviour can be altered by setting the :toml:`default_item_type` option locally on the parallel task.

Subtask outputs are streamed to the console as they arrive with a prefix identifying the task.


Available task options
----------------------

``parallel`` tasks support all of the :doc:`standard task options <../options>` with the exception of ``use_exec`` and ``capture_stdout``.

The following options are also accepted:

**ignore_fail** : ``bool`` | ``str`` :ref:`📖<Continue on subtask failure>`
  If true then the failure (or non-zero return value) of one task in the parallel group does not abort the execution.

**default_item_type** : ``str`` :ref:`📖<Changing the default item type>`
  Change the task type that is applied to string array items in this parallel group.

**prefix** : ``str`` :ref:`📖<Customize output prefixing>`
  Set the prefix applied to each line of output from subtasks. By default this is the task name.

**prefix_max** : ``int`` :ref:`📖<Customize output prefixing>`
  Set the maximum width of the prefix. Longer prefixes will be truncated. Default is 16 characters.

**prefix_template** : ``str`` :ref:`📖<Customize output prefixing>`
  Specifies a template for how the prefix is applied after truncating it to the prefix_max length. The default prefix_template is ``{color_start}{prefix}{color_end} |``


Continue on subtask failure
---------------------------

A failure (non-zero result) will result in any remaining subtasks being cancelled, unless the :toml:`ignore_fail` option is set on the task like so:

.. code-block:: toml

  [tool.poe.tasks]
  attempts.parallel = ["task1", "task2", "task3"]
  attempts.ignore_fail = true

If you want to run all the subtasks to completion but return non-zero result in the end of the sequence if any of the subtasks have failed you can set :toml:`ignore_fail` option to the :toml:`return_non_zero` like so:

.. code-block:: toml

  [tool.poe.tasks]
  attempts.parallel = ["task1", "task2", "task3"]
  attempts.ignore_fail = "return_non_zero"


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

Alternatively you can declare other task types inline like so:

.. code-block:: toml

  [tool.poe.tasks]
  parallel = [
    { script = "linters:run_mypy(all=True)" },
    { script = "linters:run_pylint" },
    { script = "linters:run_flake8" },
  ]

.. hint::

  An array within a parallel task is interpreted as a :doc:`sequence<sequence>` task, so you can run certain parallel subtasks :ref:`with strict ordering<Composing tasks to run in parallel>`.


Customize output prefixing
--------------------------

When running multiple tasks in parallel a prefix is applied to each line of output to identify the origin. By default the prefix includes the task name and has a distinct color applied to it (6 colors in rotation).

Example output:

.. raw:: html

    <div class="highlight-sh notranslate">
    <div class="highlight">
    <pre id="codecell5">
    <span style="color:red">task_1</span> | task_1 output line 1
    <span style="color:green">task_2</span> | task_2 output line 1
    <span style="color:yellow">task_3</span> | task_3 output line 1
    <span style="color:red">task_1</span> | task_1 output line 2
    <span style="color:blue">task_4</span> | task_4 output line 1
    <span style="color:yellow">task_3</span> | task_3 output line 2
    <span style="color:magenta">task_5</span> | task_5 output line 1
    <span style="color:cyan">task_6</span> | task_6 output line 1
    </pre>
    </div>
    </div>

This behavior is customizable with the following options:

- Setting the ``prefix`` changes the prefix content: default ``{name}``. The ``{index}`` tag is also available which indicates the index of the subtask within the parallel array.
- Setting the ``prefix_max`` changes the maximum width of the prefix: default ``16``
- Setting the ``prefix_template`` changes how the prefix is formatted: default ``{color_start}{prefix}{color_end} |``

For example:

.. code-block:: toml

  [tool.poe.tasks]
  parallel = ["build", "test", "deploy-to-prod"]
  prefix = "{index}:{name}"
  prefix_max = 10
  prefix_template = "[{prefix}] "

will result in output rendered like:

.. code-block::

  [1:build] first task output line
  [2:test] second task output line
  [3:deploy_…] third task output line

Note that:

1. When the ``{prefix}`` portion of the tempalate is longer that the configured ``prefix_max`` then it is truncated with ellipsis
2. omitting the ``{color_start}`` and ``{color_end}`` tags from the template disables prefix coloring.

.. hint::

  If :ref:`capture_stdout<Redirect task output to a file>` is set on a subtask then its output will of course be excluded.
