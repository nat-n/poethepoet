Installation
============

Installing Poe the Poet
-----------------------

There are a few ways to install Poe the Poet:

1. Install the CLI globally using |pipx_link| *(recommended)*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  pipx install poethepoet

Or using pip:

.. code-block:: sh

  pip install poethepoet

The ``poe`` executable will then be available anywhere in your system.

2. Install the CLI globally using |brew_link|
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``poe`` CLI is also available as a |formula_link| to be installed globally:

.. code-block:: sh

  brew tap nat-n/poethepoet
  brew install nat-n/poethepoet/poethepoet

3. Install Poe the Poet as a poetry plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  poetry self add 'poethepoet[poetry_plugin]'

It'll then be available as the :sh:`poetry poe` command anywhere in your system.

See the :doc:`poetry plugin docs <poetry_plugin>` for more details about this option.


4. Install Poe the Poet into your poetry project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sh

  poetry add --group dev poethepoet

The :sh:`poe` executable will then be available when inside a :sh:`poetry shell` or as :sh:`poetry run poe`.

.. tip::

  If you prefer not to install poe globally, then you might want to create for yourself an alias such like :sh:`alias poe="poetry run poe"` or :sh:`alias poe="poetry poe"`, which should enable you to still benefit from tab completion.

.. _shell_completion:

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
  poe _zsh_completion > ~/.zfunc/_poe

.. note::

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

Poe the Poet officially supports python >=3.9, and is tested with python 3.9 to 3.13 on
macOS, linux and windows.


.. |pipx_link| raw:: html

   <a href="https://pypa.github.io/pipx/" target="_blank">pipx</a>

.. |brew_link| raw:: html

   <a href="https://brew.sh/" target="_blank">homebrew</a>

.. |formula_link| raw:: html

   <a href="https://github.com/nat-n/homebrew-poethepoet" target="_blank">homebrew formula</a>

