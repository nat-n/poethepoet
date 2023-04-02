Installation
============

Basic Installation
------------------

There are a few ways to install Poe the Poet:

1.
  Install the CLI **globally** using pipx:

  .. code-block:: bash

    pipx install poethepoet

  Or using pip:

  .. code-block:: bash

    pip install poethepoet

  It'll then be available as the :bash:`poe` command anywhere in your system.

2.
  Install the CLI **locally** into your project (so it works inside poetry shell):

  .. code-block:: bash

    poetry add --group dev poethepoet

  It'll then be available only when inside a :bash:`poetry shell` as the :bash:`poe` command.
3.
  Install the CLI into poetry as a plugin **(requires poetry >= 1.2)**

  .. code-block:: bash

    poetry self add 'poethepoet[poetry_plugin]'

  It'll then be available as the :bash:`poetry poe` command anywhere in your system.

  More info below in the :ref:`Usage as a poetry plugin` section.

Supported python versions
-------------------------

Poe the Poet officially supports python >=3.7, and is tested with python 3.7 to 3.11 on
macOS, linux and windows.


Enable tab completion for your shell
------------------------------------

Poe comes with tab completion scripts for bash, zsh, and fish to save you keystrokes.
How to install them will depend on your shell setup.

Zsh
~~~

.. code-block:: zsh

  # oh-my-zsh
  mkdir -p ~/.oh-my-zsh/completions
  poe _zsh_completion > ~/.oh-my-zsh/completions/_poe

  # without oh-my-zsh
  mkdir -p ~/.zfunc/
  poe _zsh_completion > ~/.zfunc/_poetry

Note that you'll need to start a new shell for the new completion script to be loaded.
If it still doesn't work try adding a call to :bash:`compinit` to the end of your zshrc
file.

Bash
~~~~

.. code-block:: bash

  # System bash
  poe _bash_completion > /etc/bash_completion.d/poe.bash-completion

  # Homebrew bash
  poe _bash_completion > $(brew --prefix)/etc/bash_completion.d/poe.bash-completion


How to ensure installed bash completions are enabled may vary depending on your system.

Fish
~~~~

.. code-block:: fish

  # Fish
  poe _fish_completion > ~/.config/fish/completions/poe.fish

  # Homebrew fish
  poe _fish_completion > (brew --prefix)/share/fish/vendor_completions.d/poe.fish

Usage as a poetry plugin
------------------------

Depending on how you manage your python environments you may also wish to use Poe the
Poet in the form of a poetry plugin. This requires installing `poethepoet[poetry_plugin]`
either into the same environment as poetry or into poetry itself.
`See the poetry docs <https://python-poetry.org/docs/master/plugins/#using-plugins>`_
for more details.

Due to how the poetry CLI works (using `cleo <https://github.com/python-poetry/cleo>`_ — a
featureful but highly opinionated  CLI framework) there exist a few minor limitations
when used in this way.

1.
  Normally the poe CLI allows tasks to accept any arguments, either by defining the
  expected options or by passing any command line tokens following the task name to the
  task at runtime. This is not supported by cleo. The plugin implements a workaround
  that mostly works, but still if the `--no-plugins` option is provided *anywhere* in
  the command line then the poe plugin will never be invoked.

2.
  Poetry comes with its own
  `command line completion <https://python-poetry.org/docs/#enable-tab-completion-for-bash-fish-or-zsh>`_,
  but poe's command line completion won't work.

3.
  If you declare named arguments for your poe tasks then these are included in the
  documentation when poe is invoked without any arguments. However the inline
  documentation for poetry commands contains only the task names and help text.

Therefore it is recommended to use the poe CLI tool directly if you don't mind having
it installed onto your path.


Usage without poetry
--------------------

Poe the Poet was originally intended for use alongside poetry. But it works just as
well with any other kind of virtualenv, or simply as a general purpose way to define
handy tasks for use within a certain directory structure! This behaviour is configurable
via the :toml:`tool.poe.executor` global option (see above).

By default poe will run tasks in the poetry managed environment, if the pyproject.toml
contains a :toml:`tool.poetry` section. If it doesn't then poe looks for a virtualenv to
use from :bash:`./.venv` or :bash:`./venv` relative to the pyproject.toml file.
Otherwise it falls back to running tasks without any special environment management.

