"cmd" tasks
===========

.. note::
    The default task type is :code:`cmd`.

**Command tasks** contain a single command that will be executed without a shell.
This covers most basic use cases for example:

.. code-block:: toml

  [tool.poe.tasks]
  format = "black ."  # strings are interpreted as commands by default
  clean = """
  # Multiline commands including comments work too. Unescaped whitespace is ignored.
  rm -rf .coverage
         .mypy_cache
         .pytest_cache
         dist
         ./**/__pycache__
  """
  lint = { "cmd": "pylint poethepoet" }  # Inline tables with a cmd key work too
  greet = "echo Hello $USER"  # Environment variables work, even though there's no shell!

