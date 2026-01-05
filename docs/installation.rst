Installation
============

Installing Poe the Poet
-----------------------

There are a few ways to install Poe the Poet depending on your preferences.

1. Install the CLI globally *(recommended)*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following methods will make the ``poe`` executable available anywhere on your system.

With |pipx_link|
""""""""""""""""

.. code-block:: sh

  pipx install poethepoet


With |uv_link|
""""""""""""""

.. code-block:: sh

  uv tool install poethepoet

With |brew_link|
""""""""""""""""

.. code-block:: sh

  brew tap nat-n/poethepoet
  brew install nat-n/poethepoet/poethepoet

See the |formula_link|.

With pip
""""""""

Of course you can also install it with pip – assuming your current python environment is global.

.. code-block:: sh

  pip install poethepoet

2. Install poethepoet as a :doc:`poetry plugin<poetry_plugin>`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can install the poethepoet poetry plugin globally like so:

.. code-block:: sh

  poetry self add 'poethepoet[poetry_plugin]'

Or add it to poetry on a per project basis by adding the following to your *pyproject.toml*:

.. code-block:: sh

  [tool.poetry.requires-plugins]
  poethepoet = { version = "~0.35.0", extras = ["poetry_plugin"]}

See the |poetry_plugin_link| for more installation options, or see the :doc:`poetry plugin docs <poetry_plugin>` for more details about this option.


3. Install poethepoet into your project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With poetry
"""""""""""

.. code-block:: sh
  :caption: Add poethepoet as a dev dependency

  poetry add --group dev poethepoet

.. code-block:: sh
  :caption: And run it

  poetry run poe

With uv
"""""""

.. code-block:: sh
  :caption: Add poethepoet as a dev dependency

  uv add --dev poethepoet

.. code-block:: sh
  :caption: And run it

  uv run poe

.. _shell_completion:

Enable tab completion for your shell
------------------------------------

Poe comes with tab completion scripts for bash, zsh, and fish to save you keystrokes.
How to install them will depend on your shell setup.

.. tip::

  We believe installing the poe CLI globally offers the best developer experience. However if for some reason you prefer *not* to then you can still benefit from shell completions if you create an appropriate alias in your shell, such as one of:

  - :sh:`alias poe="poetry run poe"`
  - :sh:`alias poe="poetry poe"`
  - :sh:`alias poe="uv run poe"`

Zsh
~~~

.. code-block:: zsh

  # oh-my-zsh
  mkdir -p ~/.oh-my-zsh/completions
  poe _zsh_completion > ~/.oh-my-zsh/completions/_poe

  # without oh-my-zsh
  mkdir -p ~/.zfunc/
  poe _zsh_completion > ~/.zfunc/_poe

.. tip::

  You'll need to start a new shell for the new completion script to be loaded. If it still doesn't work try adding a call to :sh:`compinit` to the end of your zshrc file.

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


Supported python versions
-------------------------

Poe the Poet officially supports python >=3.10, and is tested with python 3.10 to 3.13 on
macOS, linux and windows.


.. |pipx_link| raw:: html

   <a href="https://pypa.github.io/pipx/" target="_blank">pipx</a>

.. |uv_link| raw:: html

   <a href="https://docs.astral.sh/uv/" target="_blank">uv</a>

.. |brew_link| raw:: html

   <a href="https://brew.sh/" target="_blank">homebrew</a>

.. |formula_link| raw:: html

   <a href="https://github.com/nat-n/homebrew-poethepoet" target="_blank">homebrew formula</a>

.. |poetry_plugin_link| raw:: html

   <a href="https://python-poetry.org/docs/main/plugins/#using-plugins" target="_blank">poetry docs</a>

