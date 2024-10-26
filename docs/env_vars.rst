Environment variables
=====================

Internal Environment variables
------------------------------

The following environment variables are used by Poe the Poet internally, and can be accessed from within configuration and tasks.

- ``POE_ROOT``: path to the parent directory of the main tasks file (e.g. pyproject.toml).
- ``POE_PWD``: the current working directory of the poe process (unless overridden programmatically).
- ``POE_CONF_DIR``: the path to the parent directory of the config file that defines the running task or the :ref:`cwd option<Setting a working directory for included tasks>` set when including that config.
- ``POE_ACTIVE``: identifies the active PoeExecutor, so that Poe the Poet can tell when it is running recursively.
- ``POE_VERBOSITY``: reflects the current verbosity level. Normally 0 is the default, 1 means more verbose and -1 means less.

Special variables
-----------------

The following variables are not set on the environment by default but can be referenced from task configuration as if they were.

- ``POE_GIT_DIR``: path of the git repo that the project is part of. This allows a project in a subdirectory of a monorepo to reference :ref:`includes<Including files relative to the git repo>` or :ref:`envfiles<Loading environment variables from an env file>` relative to the root of the git repo. Note that referencing this variable causes poe to attempt to call the ``git`` executable which must be available on the path.

- ``POE_GIT_ROOT``: just like ``POE_GIT_DIR`` except that if the project is in a git submodule, then the path will point to the working directory of the main repo above it.

External Environment variables
------------------------------

The following environment variables can be set to modify Poe the Poet's behavior.

- ``POE_PROJECT_DIR``: used as the default value for the ``--directory`` global argument.
- ``NO_COLOR``: disables ansi colors in output (unless the --ansi argument is provided).
- ``POE_DEBUG``: can be set to ``1`` to enable printing debug messages to stdout.
