``ref`` tasks
=============

A ref task is essentially a call to another task. It is the default task type within a sequence task, but is not often used otherwise.

A ref task can set environment variables, and pass arguments to the referenced task as
follows:

.. code-block:: toml

  [tool.poe.tasks]
  do_things.cmd = "do_cmd"
  do_things.args = [{ name = "things", multiple = true, positional = true }]

  do_specific_things.ref = "do_things thing1 thing2"
  do_specific_things.env = { URGENCY = "11" }


In the above example calling:

.. code-block:: sh

  poe do_specific_things

would be equivalent to executing the following in the shell:

.. code-block:: sh

  URGENCY=11 do_cmd thing1 thing2


Available task options
----------------------

``ref`` tasks support all of the :doc:`standard task options <../options>` with the exception of ``use_exec``.


Passing arguments
-----------------

By default any arguments passed to a ref task will be forwarded to the referenced task, allowing it to function as a task alias. If named arguments are configured for the ref task then additional arguments can still be passed to the referenced task after ``--`` on the command line.
