Defining tasks
==============

Poe the Poet supports several ways of defining tasks under :toml:`[tool.poe.tasks]`, trading off simplicity against configurability. Furthermore toml syntax supports both more terse or more expressive alternative ways of writing the same thing, see the guide on :doc:`../guides/toml_guide` for details.

A task defined as a string will by default be interpreted as a single command to be executed without a shell (aka a :doc:`cmd task <task_types/cmd>`).

.. code-block:: toml

  [tool.poe.tasks]
  test = "pytest"

A task defined as an array will by default be interpreted as a :doc:`sequence <task_types/sequence>` of :doc:`references<task_types/ref>` to other tasks.

.. code-block:: toml

  [tool.poe.tasks]
  test   = "pytest"
  _build = "poetry build"
  build  = ["test", "_build"] # this task runs the two referenced tasks in sequence

.. important::

   Task with names starting with an underscore ``_`` are excluded from documentation and cannot be run directly from the command line. They can only be run when referenced by another task.

Tasks can also be defined as sub-tables, which allows for specifying the task type and various configuration options on the task. The type of a task defined as a table is determined by the presence of a particular key that is unique to a certain task type and corresponds to the name of the task type.

.. code-block:: toml

  [tool.poe.tasks.test-quick]
  help = "Run tests excluding those makes as slow."
  cmd  = "pytest -m \"not slow\"" # here the cmd key identifies the task type and content

This implies that you can also define tasks of other types on a single line, like so:

.. code-block:: toml

  [tool.poe.tasks]
  tunnel.shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &" } # (posix) shell based task

:doc:`Some options <options>` are applicable to all tasks, whereas other are only applicable to :ref:`specific types of tasks<Types of task>`.

.. seealso::

   Top level tasks are defined as members of :toml:`[tool.poe.tasks]`, but sometimes tasks can be defined as children of other tasks, for example as items within a :doc:`sequence <task_types/sequence>` task, or as the ``control`` or ``case`` roles with a :doc:`switch <task_types/sequence>` task.

Types of task
-------------

You can define seven different types of task:

- :doc:`Command tasks <task_types/cmd>` :code:`cmd` : for simple commands that are executed as a subprocess without a shell

- :doc:`Script tasks<task_types/script>` :code:`script` : for python function calls

- :doc:`Shell tasks<task_types/shell>` :code:`shell` : for scripts to be executed with via an external interpreter (such as sh).

- :doc:`Sequence tasks<task_types/sequence>` :code:`sequence` : for composing multiple tasks into a sequence

- :doc:`Expression tasks<task_types/expr>` :code:`expr` : which consist of a python expression to evaluate

- :doc:`Switch tasks<task_types/switch>` :code:`switch` : for running different tasks depending on a control value (such as the platform)

- :doc:`Reference tasks<task_types/ref>` :code:`ref` : for defining a task as an alias of another task, such as in a sequence task.


.. toctree::
   :hidden:

   Standard task options <options>
   Command tasks <task_types/cmd>
   Script tasks<task_types/script>
   Shell tasks<task_types/shell>
   Sequence tasks<task_types/sequence>
   Expression tasks<task_types/expr>
   Switch tasks<task_types/switch>
   Reference tasks<task_types/ref>
