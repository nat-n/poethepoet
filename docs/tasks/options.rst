Standard task options
=====================

Overview
--------

The following options can be configured on your tasks and are not specific to any particular task type.

**help** : ``str`` | ``int`` :doc:`📖<../guides/help_guide>`
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

The envfile option accepts the name (or relative path) to a single envfile as shown
above but can also by given a list of such paths like so:

.. code-block:: toml

    serve.envfile = [".env", "local.env"]

In this case the referenced files will be loaded in the given order.

Normally envfile paths are resolved relative to the project root (that is the parent directory of the pyproject.toml). However when working with a monorepo it can also be useful to specify the path relative to the root of the git repository, which can be done by referenceing the ``POE_GIT_DIR`` or ``POE_GIT_ROOT`` variables like so:

.. code-block:: toml

    [tool.poe]
    envfile = "${POE_GIT_DIR}/.env"

See the documentation on :ref:`Special variables<Special variables>` for a full explanation of how these variables work.

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

