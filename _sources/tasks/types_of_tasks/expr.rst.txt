"expr" tasks
============

Expr tasks consist of a single `python expression <https://docs.python.org/3/reference/expressions.html>`_. Running the task evaluates the expression and outputs the resulting
value. Here's a trivial example of an expr task that will print 2 when run:

.. code-block:: toml

  [tool.poe.tasks.trivial-example]
  expr = "1 + 1"

.. code-block:: bash

  $ poe trivial-example
  Poe => 1 + 1
  2

Expressions can:

- use most python expression constructs with the exception of yield, await, or named
  expressions
- use most builtin functions including all members of
  `this collection <https://github.com/nat-n/poethepoet/blob/main/poethepoet/helpers/python.py#L13>`_
- reference the sys module without having to specify it as an import
- reference sys.argv to get whatever arguments were passed to the task, just like in
  script tasks
- referene values of named args as python variables
- include environment variables as string values that are injected into the expression
  using the usual templating syntax

Referencing arguments and environment variables
-----------------------------------------------

The expression can reference environment variables using templating syntax like in cmd
tasks, and named arguments as python variables in scope like in script tasks.

.. code-block:: toml

  [tool.poe.tasks.venv-active]
  expr = """(
    f'{target_venv} is active'
    if ${VIRTUAL_ENV}.endswith(target_venv)
    else f'{target_venv} is not active'
  )"""
  args = [{ name = "target-venv", default = ".venv", positional = true }]

.. code-block::

  $ poe venv-active poethepoet-LCpCQf8S-py3.10
  Poe => (
    f'{target_venv} is active'
    if ${VIRTUAL_ENV}.endswith(target_venv)
    else f'{target_venv} is not active'
  )
  poethepoet-LCpCQf8S-py3.10 is not active

In this example the :code:`VIRTUAL_ENV` environment variable is templated into the
expression using the usual templating syntax, and the :code:`target_venv` argument is
referenced directly as a variable.

Notice that the expression may be formatted over multiple lines, as in normal python
code.

Referencing imported modules in an expression
---------------------------------------------

By default the sys module is available to the expression which allows access to sys.argv
or sys.platform amoung other useful values. However you can also reference any other
importable module via the imports option as in the following example.

.. code-block:: toml

  [tool.poe.tasks.count-hidden]
  help    = "Count hidden files or subdirectories"
  expr    = "len(list(pathlib.Path('.').glob('.*')))"
  imports = ["pathlib"]

Fail if the expression result is falsey
---------------------------------------

The expression can be made to behave like an assertion that fails if the result is not truthy by providing the assert option. The task defined in the following example will
return non-zero if the result is False.

.. code-block:: toml

  [tool.poe.tasks.venv-active]
  expr   = "${VIRTUAL_ENV}.endswith(target_venv)"
  assert = true
  args   = [{ name = "target-venv", default = ".venv", positional = true }]

Referencing the result of other tasks in an expression
------------------------------------------------------

Expr tasks can reference the results of other tasks by leveraging the :code:`uses`
option.

.. code-block:: toml

  [tool.poe.tasks._get_active_session]
  cmd = "read_session --format json"

  [tool.poe.tasks.show-user]
  expr    = """(
    f"User: {json.loads(${SESSION_JSON})['User']}"
    if len(${SESSION_JSON}) > 2
    else "No active session."
  )"""
  uses    = { SESSION_JSON = "_get_active_session" }
  imports = ["json"]


