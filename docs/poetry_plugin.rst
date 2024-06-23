Poetry plugin
=============

Depending on how you manage your python environments you may also wish to use Poe the
Poet in the form of a |poetry_plugin_link|.

.. code-block:: sh

  poetry self add 'poethepoet[poetry_plugin]'

Configuring the plugin
----------------------

By default the poetry plugin will register *poe* as a command prefix so tasks can be
invoked like:

.. code-block:: sh

  poetry poe [task_name] [task_args]

And the poe documentation can be viewed via:

.. code-block:: bash

  poetry poe

It is also possible to modify this behavior, to either have a different command prefix
or none at all by setting the :toml:`poetry_command` global option in your
pyproject.toml like so:

.. code-block:: toml

  [tool.poe]
  poetry_command = ""

In this case poe tasks will be registered as top level commands on poetry and can be
invoked simply as:

.. code-block:: sh

  poetry [task_name]

.. warning::
    Whatever :toml:`tool.poe.poetry_command` is set to must not already exist as a
    poetry command!

    Additionally if setting it to the empty string then care must be taken to avoid
    defining any poe tasks that conflict with any other built in or plugin provided
    poetry command.

Hooking into poetry commands
----------------------------

It is also possible to configure a task to be run before or after a specific poetry
command by declaring the ``poetry_hooks`` global option like so:

.. code-block:: toml

  [tool.poe.poetry_hooks]
  pre_build  = "prep-assets --verbosity=5"
  post_build = "archive-build"

  [tool.poe.tasks.prep-assets]
  script = "scripts:prepare_assets"
  help   = "Optimise static assets for inclusion in the build"

  [tool.poe.tasks.archive-build]
  script = "scripts:archive_build"
  help   = "Upload the latest build version to the archive server"

In this example the ``prep-assets`` task will be run as the first step when calling
:sh:`poetry build` with an argument passed as if the task were being called via the
poe CLI. We've also configured the ``archive-build`` task to be run after every
successful build.

If a task fails when running as a hook, then the poetry command will exit with an error.
If it is a *pre* hook then this will cause the actual poetry command not to execute.
This behaviour may be useful for running checks before :bash:`poetry publish`

Hooks can be disabled for a single invocation by passing the :bash:`--no-plugins` option
to poetry.

Namespaced commands like :bash:`poetry env info` can be specified with underscores like so:

.. code-block:: toml

  [tool.poe.poetry_hooks]
  post_env_info = "info"

All poetry commands are supported in principle.

Known limitations
-----------------

Due to how the poetry CLI works (using |cleo_link| — a
featureful but highly opinionated CLI framework) there exist a few minor limitations
to consider when using the Poe the Poet poetry plugin.

1.
  Normally the poe CLI allows tasks to accept any arguments, either by defining the
  expected options or by passing any command line tokens following the task name to the
  task at runtime. This is not supported by cleo. The plugin implements a workaround
  that mostly works, but still if the `--no-plugins` option is provided *anywhere* in
  the command line then the poe plugin will never be invoked.

2.
  Poetry comes with its own |poetry_comp_link|, which includes completion of task names but poe's command line completion won't work.

3.
  If you declare named arguments for your poe tasks then these are included in the
  documentation when poe is invoked without any arguments. However the inline
  documentation for poetry commands contains only the task names and help text.

Therefore it is generally recommended to use the poe CLI tool directly if you don't mind having it installed onto your path.



.. |cleo_link| raw:: html

   <a href="https://github.com/python-poetry/cleo" target="_blank">cleo</a>

.. |poetry_comp_link| raw:: html

   <a href="https://python-poetry.org/docs/#enable-tab-completion-for-bash-fish-or-zsh" target="_blank">command line completion</a>

.. |poetry_plugin_link| raw:: html

   <a href="https://python-poetry.org/docs/main/plugins/#using-plugins" target="_blank">poetry plugin</a>
