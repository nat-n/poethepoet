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

Zsh completion includes:

- Global CLI options (``-v``, ``-C``, etc.)
- Task names with help text descriptions
- Task-specific arguments (options and positional args)

.. tip::

  You'll need to start a new shell for the new completion script to be loaded. If it still doesn't work try adding a call to :sh:`compinit` to the end of your zshrc file.

  In some cases when upgrading to a newer version of the completion script it may be necessary to clean the zsh completions cache with `rm ~/.zcompdump*`

Bash
~~~~

.. code-block:: bash

  # Quick setup - add to ~/.bashrc
  eval "$(poe _bash_completion)"

  # Or install to a file (requires new shell to take effect):

  # User local (recommended)
  mkdir -p ~/.local/share/bash-completion/completions
  poe _bash_completion > ~/.local/share/bash-completion/completions/poe

  # System-wide
  poe _bash_completion | sudo tee /etc/bash_completion.d/poe > /dev/null

  # Homebrew bash
  poe _bash_completion > $(brew --prefix)/etc/bash_completion.d/poe

Bash completion includes:

- Global CLI options (``-v``, ``-C``, etc.)
- Task names
- Task-specific arguments and choices

.. tip::

  If completions don't work after installing to a file, ensure you have the ``bash-completion`` package installed and that it's sourced in your ``~/.bashrc``. You may need to start a new shell session.

Fish
~~~~

.. code-block:: fish

  # Fish
  poe _fish_completion > ~/.config/fish/completions/poe.fish

  # Homebrew fish
  poe _fish_completion > (brew --prefix)/share/fish/vendor_completions.d/poe.fish

Powershell
~~~~~~~~~~

.. code-block:: pwsh

  # add to $PROFILE
  poe _powershell_completion | out-string | invoke-expression


Powershell completion includes:

- Global CLI options (``-v``, ``-C``, etc.)
- Task names
- Task-specific arguments and choices

.. tip::

  You'll need to start a new shell for the new completion script to be loaded. Alternatively, you can invoke ``. $PROFILE`` to reload your profile.

Supported python versions
-------------------------

Poe the Poet officially supports python >=3.10, and is tested with python 3.10 to 3.14 on
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

