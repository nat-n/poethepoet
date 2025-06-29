``cmd`` tasks
=============

**Command tasks** contain a single command that will be executed as a sub-process without a shell. This covers most basic use cases such as the following examples.

.. code-block:: toml

  [tool.poe.tasks.test]
  cmd = "pytest -v tests"

.. note::

  Tasks defined as just a string value, are interpreted as ``cmd`` tasks by default.


Available task options
----------------------

``cmd`` tasks support all of the :doc:`standard task options <../options>`.

The following options are also accepted:

**empty_glob** : ``Literal["pass", "null", "fail"]`` :ref:`📖<Glob expansion>`
  Determines how to handle glob patterns with no matches. The default is ``"pass"``, which causes unmatched patterns to be passed through to the command (just like in bash). Setting it to ``"null"`` will replace an unmatched pattern with nothing, and setting it to ``"fail"`` will cause the task to fail with an error if there are no matches.


Shell like features
-------------------

It is important to understand that ``cmd`` tasks are executed without a shell (to maximise portability). However some shell like features are still available including basic parameter expansion and pattern matching. Quotes and escapes are also generally interpreted as one would expect in a shell.

.. _ref_env_vars:


Referencing environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Environment variables can be templated into the command. Just like in bash: whitespace inside a variable results in a word break, and glob patterns are evaluated after parameter expansion, unless the parameter expansion is inside double quotes. Single quotes disable parameter expansion. Curly braces are recommended but optional.

.. code-block:: toml

  [tool.poe.tasks]
  greet = "echo Hello ${USER}"

.. code-block:: sh

  $ poe greet
  Poe => echo Hello nat
  Hello nat

Parameter expansion can also can be disabled by escaping the $ with a backslash like so:

.. code-block:: toml

  [tool.poe.tasks]
  greet = "echo Hello \\$USER"  # the backslash itself needs escaping for the toml parser


Parameter expansion operators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When referencing an environment variable in a cmd task you can use the ``:-`` operator from bash to specify a *default value*, to be used in case the variable is unset. Similarly the ``:+`` operator can be used to specify an *alternate value* to use in place of the environment variable if it *is* set.

In the following example, if ``AWS_REGION`` has a value then it will be used, otherwise ``us-east-1`` will be used as a fallback.

.. code-block:: toml

  [tool.poe.tasks]
  tables = "aws dynamodb list-tables --region ${AWS_REGION:-us-east-1}"

The ``:+`` or *alternate value* operator is especially useful in cases such as the following where you might want to control whether some CLI options are passed to the command.

.. code-block:: toml

  [tool.poe.tasks.aws-identity]
  cmd = "aws sts get-caller-identity ${ARN_ONLY:+ --no-cli-pager --output text --query 'Arn'}"
  args = [{ name = "ARN_ONLY", options = ["--arn-only"], type = "boolean" }]

In this example we declare a boolean argument with no default, so if the ``--arn-only`` flag is provided to the task then three additional CLI options will be included in the task content.


Glob expansion
~~~~~~~~~~~~~~

Glob patterns in cmd tasks are expanded and replaced with the list of matching files and directories. Glob patterns are evaluated relative to the working directory of the task.

The supported glob syntax is that of the |glob_link|, which differs from bash in that square bracket patterns don't support character classes, don't break on whitespace, and don't allow escaping of contained characters.

If there are no matches then by default the pattern is passed through to the command unchanged (just like in bash). This behavior can be overridden for a specific task by setting the :toml:`empty_glob` option to ``"null"`` or ``"fail"``. If set to ``"null"`` then the pattern will be replaced with nothing (similar to how bash behaves with the |nullglob_link| is set), and if set to ``"fail"`` then a glob pattern with no matches will cause the task execution will fail with an error.

The following task uses glob patterns to specify all ``.pyc`` files and ``__pycache__`` directories in the project in the project for removal, and thanks to the :toml:`empty_glob` options it will succeed even if there are no matches since no arguments will be passed to the ``rm`` command.

.. code-block:: toml

  [tool.poe.tasks.clean]
  cmd = """
  rm -rf ./**/*.pyc
         ./**/__pycache__    # this will match all __pycache__ dirs in the project
  """
  empty_glob = "null"

.. code-block:: sh

  $ poe clean
  Poe => rm -rf ./tests/__pycache__ ./docs/__pycache__ ...

.. seealso::

  Notice that this example also demonstrates that comments and excess whitespace (including new lines) are ignored, without needing to escape new lines.

.. tip::

  Just like in bash, the glob pattern can be escaped by wrapping it in quotes, or preceding it with a backslash.


.. |glob_link| raw:: html

   <a href="https://docs.python.org/3/library/glob.html" target="_blank">python standard library glob module</a>

.. |nullglob_link| raw:: html

   <a href="https://www.gnu.org/software/bash/manual/html_node/Filename-Expansion.html" target="_blank">nullglob option</a>
