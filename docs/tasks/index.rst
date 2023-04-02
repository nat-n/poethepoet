Types of Task
=============

You can define seven different types of task:

- :doc:`Command tasks <types_of_task/cmd>` :code:`cmd` : for simple commands that are executed as a subprocess without a shell

- :doc:`Script tasks<types_of_task/script>` (:code:`script`) for python function calls

- :doc:`Shell tasks<types_of_task/shell>` (:code:`shell`) for scripts to be executed with via an external interpreter (such as sh).

- :doc:`Sequence tasks<types_of_task/sequence>` (:code:`sequence`) for composing multiple tasks into a sequence

- :doc:`Expression tasks<types_of_task/expr>` (:code:`expr`) which consist of a python expression to evaluate

- :doc:`Switch tasks<types_of_task/switch>` (:code:`switch`) for running different tasks depending on a control value (such as the platform)

- :doc:`Reference tasks<types_of_task/ref>` (:code:`ref`): for defining a task as an alias of another task, such as in a sequence task.




.. toctree::
   :hidden:

   Command tasks <types_of_task/cmd>
   Script tasks<types_of_task/script>
   Shell tasks<types_of_task/shell>
   Sequence tasks<types_of_task/sequence>
   Expression tasks<types_of_task/expr>
   Switch tasks<types_of_task/switch>
   Reference tasks<types_of_task/ref>
