Standard task options
=====================

Overview
--------

The following options can be configured on your tasks and are not specific to any particular task type.

**help** : ``str`` :doc:`📖<../guides/help_guide>`
  Help text to be displayed next to the task name in the documentation when poe is run without specifying a task.

**args** : ``dict[str, dict]`` | ``list[Union[str, dict]]`` :doc:`📖<../guides/args_guide>`
  Define CLI options, positional arguments, or flags that this task should accept.

**env** :  ``dict[str, str]`` :ref:`📖<Setting task specific environment variables>`
  A map of environment variables to be set for this task.

**envfile** :  ``str`` | ``list[str]`` :ref:`📖<Loading environment variables from an env file>`
  Provide one or more env files to be loaded before running this task.

**cwd** :  ``str`` :ref:`📖<Running a task with a specific working directory>`
  Specify the current working directory that this task should run with. The given path is resolved relative to the parent directory of the ``pyproject.toml``, or it may be absolute.
  Resolves environment variables in the format ``${VAR_NAME}``.

**deps** :  ``list[str]`` :doc:`📖<../guides/composition_guide>`
  A list of task invocations that will be executed before this one.

**uses** :  ``dict[str, str]`` :doc:`📖<../guides/composition_guide>`
  Allows this task to use the output of other tasks which are executed first.
  The value is a map where the values are invocations of the other tasks, and the keys are environment variables by which the results of those tasks will be accessible in this task.

**capture_stdout** : ``str`` :ref:`📖<Redirect task output to a file>`
  Causes the task output to be redirected to a file with the given path.

**executor** : ``str`` | ``dict[str, str]`` :ref:`📖<Configure the executor for a task>`
  Specify executor type and/or configuration for this task.

**verbosity** : ``int`` :ref:`📖<Configure task level verbosity>`
  Specify the verbosity level for this task, from -2 (least verbose) to 2 (most verbose), overriding the project level verbosity setting, which defaults to 0.

**use_exec** : ``bool`` :ref:`📖<Defining tasks that run via exec instead of a subprocess>`
  Specify that this task should be executed in the same process, instead of as a subprocess.

  .. attention::

    This option is only applicable to **cmd**, **script**, and **expr** tasks, and it implies the task in question cannot be referenced by another task.

Setting task specific environment variables
-------------------------------------------

You can specify arbitrary environment variables to be set for a single task by providing the env option like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    script = "myapp:run"
    env = { PORT = "9001" }

Notice this example uses deep keys which can be more convenient but aren't as well supported by some older toml implementations.


Setting defaults for environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The previous example can be modified to only set the `PORT` variable if it is not already set by replacing the last line with the following:

.. code-block:: toml

    env.PORT.default = "9001"


Templating environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is also possible to reference existing environment variables when defining a new environment variable for a task. This may be useful for aliasing or extending a variable already defined in the host environment, globally in the config, or in a referenced envfile. In the following example the value from $TF_VAR_service_port on the host environment is also made available as $FLASK_RUN_PORT within the task.

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd = "flask run"
    env = { FLASK_RUN_PORT = "${TF_VAR_service_port}" }


.. _envfile_option:

Loading environment variables from an env file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also specify one or more env files (with bash-like syntax) to load per task like so:

.. code-block:: bash

    # .env
    STAGE=dev
    PASSWORD='!@#$%^&*('

.. code-block:: toml

    [tool.poe.tasks]
    serve.script  = "myapp:run"
    serve.envfile = ".env"

The envfile option accepts the name (or relative path) to a single envfile as shown above but can also by given a list of such paths like so:

.. code-block:: toml

    serve.envfile = [".env", "local.env"]

Normally a missing envfile results in a warning, however optional envfiles can be indicated with the following structure including the ``optional`` key, in contrast with the ``expected`` key:

.. code-block:: toml

    [tool.poe.tasks.serve.envfile]
    optional = ["local.env"]
    expected = ["base.env"]

Files are loaded in the listed order, optional files are loaded after expected files. Last file wins in case of conflicts.

Normally envfile paths are resolved relative to the project root (that is the parent directory of the pyproject.toml). However when working with a monorepo it can also be useful to specify the path relative to the root of the git repository, which can be done by referencing the ``POE_GIT_DIR`` or ``POE_GIT_ROOT`` variables like so:

.. code-block:: toml

    [tool.poe]
    envfile = "${POE_GIT_DIR}/.env"

See the documentation on :ref:`Special variables<Special variables>` for a full explanation of how these variables work.

.. important::

  For a more detailed explanation see the documentation for :ref:`the envfile global option<Loading external environment variables>` which works in the same way.


Running a task with a specific working directory
------------------------------------------------

By default tasks are run from the project root – that is the parent directory of the pyproject.toml file. However if a task needs to be run in another directory then this can be accomplished by using the :toml:`cwd` option like so:

.. code-block:: toml

    [tool.poe.tasks.build-client]
    cmd = "npx ts-node -T ./build.ts"
    cwd = "./client"

In this example, the npx executable is executed inside the :sh:`./client` subdirectory of the project (when ``cwd`` is a relative path, it gets resolved relatively to the project root), and will use the nodejs package.json configuration from that location and evaluate paths relative to that location.

The ``cwd`` option also accepts absolute paths and resolves environment variables in the format ``${VAR_NAME}``.

Poe provides its own :sh:`$POE_PWD` variable that is by default set to the directory, from which poe was executed; this may be overridden by setting the variable to a different value beforehand. Using :sh:`$POE_PWD`, a task's working directory may be set to the one from which it was executed like so:

.. code-block:: toml

    [tool.poe.tasks.convert]
    script = "my_project.conversion_tool:main"
    cwd = "${POE_PWD}"


Redirect task output to a file
------------------------------

You can configure poe to redirect the standard output of a task to a file on disk by providing the ``capture_stdout`` option like so.

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd            = "gunicorn ./my_app:run"
    capture_stdout = "gunicorn_log.txt"

If a relative path is provided, as in the example above, then it will be resolved relative to the project root directory.

The ``capture_stdout`` option supports referencing environment variables. For example setting ``capture_stdout = "${POE_PWD}/output.txt"`` will cause the output file to be created within the current working directory of the parent process.

.. warning::

  The ``capture_stdout`` is incompatible with the ``use_exec`` option, and tasks that declare it cannot be referenced by another task via the ``uses`` option.

The value ``/dev/null`` or ``NUL`` may be used to discard all output from the task.


Configure the executor for a task
---------------------------------

You can specify a different executor for a task by providing the ``executor`` option like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd      = "gunicorn ./my_app:run"
    executor = { type = "virtualenv", location = "./server.venv" }

This works exactly like the the global option to :ref:`configure the executor<Configure the executor>` except it only impacts the one task. If the task does not specify a different executor type, then it will inherit from and extend the global executor configuration (assuming the type is the same).

If you only want to change the executor type but not provide any additional configuration, you can also specify the executor as a simple string like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd      = "gunicorn ./my_app:run"
    executor = "poetry"

Configure task level virtualenv with uv
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The uv executor supports configuring uv to run a task with its own environment. This is a powerful feature that allows Poe the Poet + uv to be used as a :ref:`lightweight alternative to tools like tox<Replacing tox with uv and Poe the Poet>` for testing against multiple python versions or dependency sets.

.. code-block:: toml

    [tool.poe]
    executor = "uv"

    [tool.poe.tasks.test-py311]
    help     = "An alias for the test task that runs with python 3.11"
    cmd      = "pytest"
    executor = {isolated = true, python = "3.11"}

    [tool.poe.tasks.test-py312]
    help     = "An alias for the test task that runs with python 3.12"
    cmd      = "pytest"
    executor = {isolated = true, python = "3.12"}

    [tool.poe.tasks.test-matrix]
    help     = "Run tests for all python versions"
    sequence = ["test-py311", "test-py312"]

Note that it is not necessary to specify ``type = "uv"`` in the executor configuration if the project is already configured to use the uv executor by default.

You can also specify a dependency on the task level without needing to add it as a project dependency, using the ``with`` option like so:

.. code-block:: toml

    [tool.poe.tasks.test]
    help     = "Run the tests"
    cmd      = "pytest"
    executor = {type = "uv", with = ["pytest"], isolated = true}

Executor options can also be set at runtime via the ``--executor-opt`` CLI option (before the task name) to override or add to the executor configuration for a specific task invocation.

.. code-block:: bash

    poe --executor uv --executor-opt with=pytest --executor-opt isolated --executor-opt with=pytest-cov --executor-opt python=3.12 test --cov my_package

Multiple values can be provided for options that accept lists by passing the ``--executor-opt`` option multiple times as shown above.


Configure task level verbosity
------------------------------

You can specify the verbosity level for a task by providing the :toml:`verbosity` option like so:

.. code-block:: toml

    [tool.poe.tasks.credentials]
    cmd       = "aws secretsmanager get-secret-value --secret-id creds --query 'SecretString'"
    verbosity = -1

This overrides the project level verbosity setting, which defaults to 0. The verbosity level can be set to an integer from -2 (least verbose) to 2 (most verbose).

Passing the ``-v`` or ``-q`` global options (before the task name on the command line) will override increment or decrement all verbosity levels.


Verbosity levels
~~~~~~~~~~~~~~~~

The verbosity level is an integer, where positive values increase the verbosity of the output, and negative values decrease it. The levels are as follows:

- -3 : suppress all output, including errors
- -2 : suppress warning messages
- -1 : suppress info messages such as those describing which tasks are being run
- 0 : standard verbosity
- 1 : some extra details in output
- 2 : more extra details in output
- 3 : debug output referencing poethepoet internals (similar to setting ``POE_DEBUG=1``)

Note that the verbosity level only applies to output from poethepoet itself, and does not impact the output of the tasks being run.

Inline tasks (such as those defined within a sequence task) inherit the verbosity level of their parent task, unless they explicitly override it.

The verbosity modifying global cli options may be provided multiple times to increment or decrement the verbosity level by 1 for each occurrence. For example, running ``poe -qq test`` will run the ``test`` task with a verbosity level of -2 relative to the baseline otherwise specified for the project or task.

Defining tasks that run via exec instead of a subprocess
--------------------------------------------------------

Normally tasks are executed as subprocesses of the ``poe`` executable. This makes it possible for poe to run multiple tasks, for example within a sequence task or task graph.

However in certain situations it can be desirable to define a task that is instead executed within the same process via an *exec* call. :doc:`task_types/cmd` and :doc:`task_types/script` tasks can be configured to work this way using the :toml:`use_exec` option like so:

.. code-block:: toml

    [tool.poe.tasks.serve]
    cmd      = "gunicorn ./my_app:run"
    use_exec = true

.. warning::

  Note the following limitations with this feature:

  1. a task configured in this way may not be referenced by another task
  2. this does not work on windows because of `this issue <https://bugs.python.org/issue19066>`_. On windows a subprocess is always created.
