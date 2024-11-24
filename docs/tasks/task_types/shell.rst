``shell`` tasks
===============

**Shell tasks** are similar to simple command tasks except that they are executed inside a new shell, and can consist of multiple statements. This means they can leverage the full syntax of the shell interpreter such as command substitution, pipes, background processes, etc.

An example use case for this might be opening some ssh tunnels in the background with one task and closing them with another like so:

.. code-block:: toml

  [tool.poe.tasks.pfwd]
  shell = """
    ssh -N -L 0.0.0.0:8080:$STAGING:8080 $STAGING &
    ssh -N -L 0.0.0.0:5432:$STAGINGDB:5432 $STAGINGDB &
  """

  [tool.poe.tasks.pfwdstop]
  shell = "kill $(pgrep -f "ssh -N -L .*:(8080|5432)")"

.. seealso::

    By default poe attempts to find a posix shell (sh, bash, or zsh in that order) on the system and uses that. When running on windows, poe will first look for |git_bash_link| at the usual location, and otherwise attempt to find it via the PATH, though this might not always be possible.


Available task options
----------------------

``shell`` tasks support all of the :doc:`standard task options <../options>` with the exception of ``use_exec``.

The following options are also accepted:

**interpreter** : ``str`` | ``list[str]`` :ref:`📖<Using a different shell interpreter>`
  Specify the shell interpreter that this task should execute with, or a list of interpreters in order of preference.


Using a different shell interpreter
-----------------------------------

It is also possible to specify an alternative interpreter (or list of compatible interpreters ordered by preference) to be invoked to execute shell task content. For example if you only expect the task to be executed on windows or other environments with powershell installed then you can specify a powershell based task like so:

.. code-block:: toml

  [tool.poe.tasks.install-poetry]
  shell = """
  (Invoke-WebRequest -Uri https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py -UseBasicParsing).Content | python -
  """
  interpreter = "pwsh"

If your task content is restricted to syntax that is valid for both posix shells and powershell then you can maximise the likelihood of it working on any system by specifying the interpreter as:

.. code-block:: toml

  interpreter = ["posix", "pwsh"]

It is also possible to specify python code as the shell task code as in the following example. However it is recommended to use a :doc:`script<script>` or :doc:`expr<expr>` task rather than writing complex code inline within your pyproject.toml.

.. code-block:: toml

  [tool.poe.tasks.time]
  shell = """
  from datetime import datetime

  print(datetime.now())
  """
  interpreter = "python"

The following interpreter values may be used:

posix
    This is the default behavior, equivalent to ``["sh", "bash", "zsh"]``, meaning that poe will try to find sh, and fallback to bash, then zsh.
sh
    Use the basic posix shell. This is often an alias for either bash or dash depending on the operating system.
bash
    Uses whatever version of bash can be found. This is usually the most portable option.
zsh
    Uses whatever version of zsh can be found.
fish
    Uses whatever version of fish can be found.
pwsh
    Uses powershell version 6 or higher.
powershell
    Uses the newest version of powershell that can be found.

The default value can be changed with the global ``shell_interpreter`` option.


.. |git_bash_link| raw:: html

   <a href="https://gitforwindows.org" target="_blank">git bash</a>
