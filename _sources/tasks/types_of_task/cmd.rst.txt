``cmd`` tasks
=============

**Command tasks** contain a single command that will be executed as a sub process without a shell.
This covers most basic use cases such as the following examples.

.. code-block:: toml

  [tool.poe.tasks.test]
  cmd = "pytest -v tests"

.. note::

  Tasks defined as just a string value, are interpreted as ``cmd`` tasks by default.

Available task options
----------------------

``cmd`` tasks support all of the :doc:`standard task options <../options>`.


Shell like features
-------------------

It it important to understand that ``cmd`` tasks are executed without a shell (to maximise portability). However some shell like features are still available.

Referencing environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Environment variables can be referenced using shell like syntax and are templated into the command.

.. code-block:: toml

  [tool.poe.tasks]
  greet = "echo Hello ${USER}"


.. code-block:: sh

  $ poe greet
  Poe => echo Hello nat
  Hello nat

Parsing of variable referenced can be ignored by escaping with a backslash like so:


.. code-block:: toml

  [tool.poe.tasks]
  greet = "echo Hello \\${USER}"  # the backslash itself needs escaping for the toml parser


Glob expansion
~~~~~~~~~~~~~~

Glob patterns in cmd tasks are expanded and replaced with their results.

.. code-block:: toml

  [tool.poe.tasks]
  clean = """
  rm -rf ./**/*.pyc
         ./**/__pycache__    # this will match all __pycache__ dirs in the project
  """


.. code-block:: sh

  $ poe greet
  Poe => rm -rf ./tests/__pycache__ ./docs/__pycache__ ...

.. seealso::

  Notice that this example also demonstrates that comments and excess whitespace (including new lines) are ignored.

.. seealso::

  Much like in a POSIX shell, the glob pattern can be escaped by wrapping it in single quotes.
