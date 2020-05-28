Tasks
=====

There are seven types of task:

- **Command tasks** (:code:`cmd`) for simple commands that are executed as a subprocess without a shell

- **Script tasks** (:code:`script`) for python function calls

- **Shell tasks** (:code:`shell`) for scripts to be executed with via an external interpreter (such as sh).

- **Sequence tasks** (:code:`sequence`) for composing multiple tasks into a sequence

- **Expression tasks** (:code:`expr`) which consist of a python expression to evaluate

- **Switch tasks** (:code:`switch`) for running different tasks depending on a control value (such as the platform)

- **Ref tasks** (:code:`ref`): used for defining a task as an alias of another task, such as in a sequence task.

.. toctree::
   :maxdepth: 2
   :glob:

   ./types_of_tasks/*