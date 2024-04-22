Environment variables
=====================

Internal Environment variables
------------------------------

The following environment variables are used by Poe the Poet internally, and can be accessed from within configuration and tasks.

- ``POE_ROOT``: path to the parent directory of the main tasks file (e.g. pyproject.toml).
- ``POE_PWD``: the current working directory of the poe process (unless overriden programmatically).
- ``POE_CONF_DIR``: the path to the parent directory of the config file that defines the running task or the :ref:`cwd option<Setting a working directory for included tasks>` set when including that config.
- ``POE_ACTIVE``: identifies the active PoeExecutor, so that Poe the Poet can tell when it is running recursively.

External Environment variables
------------------------------

The following environment variables can be set to modify Poe the Poet's behavior.

- ``POE_PROJECT_DIR``: used as the default value for the ``--directory`` global argument.
- ``NO_COLOR``: disables ansi colors in output (unless the --ansi argument is provided).
- ``POE_DEBUG``: can be set to ``1`` to enable printing debug messages to stdout.
