Environment variables
=====================


How Poe the Poet uses environment variables
-------------------------------------------

Poe tasks inherit environment variables from the host shell, but tasks also run with additional variables that are provided via the following channels, ordered with ascending precedence. The principle for precedence is that variables closer to the task override those further away.

1. Host environment variables (what poe receives as ``os.environ``)
2. Project level :ref:`env files<Loading external environment variables>` (in the order listed)
3. Project level :ref:`env config<Global environment variables>`
4. Parent task variables
5. Task level :ref:`env files<envfile_option>`
6. Task level :ref:`env config<Setting task specific environment variables>`
7. Output values from tasks configured as dependencies via the :doc:`uses<guides/composition_guide>` option
8. Variables set by task :doc:`args<guides/args_guide>`

As well as being exposed to the task at runtime, environment variables can also be templated into some other task configuration fields.

For ``cmd`` tasks expansion of variables via bash parameter expansion syntax is performed as part of resolving the command to run as a subprocess.

Private variables
~~~~~~~~~~~~~~~~~

Variables that start with ``_`` and contain no uppercase characters are treated as private, which means that they're available for use in configuration time (which includes parameter expansion within ``cmd`` tasks), but are not exposed to the task subprocess at runtime. This applies to all variables set via project or task level configuration.

It is a good practice to use private variable names for ``args`` or ``uses`` unless you specifically want those values to be set on the task environment.

In the following example, the ``_food`` arg will cause the task to accept an option like ``--food sausages``, and will be accessible as a variable in the task config, but not as an environment variable at runtime.

.. code-block:: toml

   [tool.poe.tasks.cook]
   script = "kitchen:frying_pan(_food)"
   args = [{ name = "_food", default = "eggs" }]


Variables managed by Poe the Poet
---------------------------------

Internal Environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following environment variables are used by Poe the Poet internally, and can be accessed from within configuration and tasks.

- ``POE_ROOT``: path to the parent directory of the main tasks file (e.g. pyproject.toml).
- ``POE_PWD``: the current working directory of the poe process (unless overridden programmatically).
- ``POE_CONF_DIR``: the path to the parent directory of the config file that defines the running task or the :ref:`cwd option<Setting a working directory for included tasks>` set when including that config.
- ``POE_ACTIVE``: identifies the active PoeExecutor, so that Poe the Poet can tell when it is running recursively.
- ``POE_VERBOSITY``: reflects the current verbosity level. Normally 0 is the default, 1 means more verbose and -1 means less.

Special variables
~~~~~~~~~~~~~~~~~

The following variables are not set on the environment by default but can be referenced from task configuration as if they were.

- ``POE_GIT_DIR``: path of the git repo that the project is part of. This allows a project in a subdirectory of a monorepo to reference :ref:`includes<Including files relative to the git repo>`, :ref:`envfiles<Loading environment variables from an env file>`, or :ref:`virtualenv location<Configure the executor for a task>` relative to the root of the git repo. Note that referencing this variable causes poe to attempt to call the ``git`` executable which must be available on the path.

- ``POE_GIT_ROOT``: just like ``POE_GIT_DIR`` except that if the project is in a git submodule, then the path will point to the working directory of the main repo above it.

External Environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following environment variables can be set to modify Poe the Poet's behavior.

- ``POE_PROJECT_DIR``: used as the default value for the ``--directory`` global argument.
- ``NO_COLOR``: disables ansi colors in output (unless the --ansi argument is provided).
- ``POE_DEBUG``: can be set to ``1`` to enable printing debug messages to stdout.
