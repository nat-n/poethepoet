Global tasks
============

This guide covers how to use poethepoet as a global task runner, for private user level tasks instead of shared project level tasks. Global tasks are available anywhere, and serve a similar purpose to shell aliases or scripts on the ``PATH`` — but as poe tasks.

There are two steps required to make this work:

1. Create a project somewhere central such as ``~/.poethepoet`` where you define tasks that you want to have globally accessible
2. Configure an alias in your shell's startup script such as ``alias edgar="poe -C ~/.poethepoet"``.

.. tip::

  This document suggests calling your alias `edgar` — because it's a pun... but you can use any alternative name you fancy.

The project at ``~/.poethepoet`` can be a regular poetry project including dependencies or just a file with tasks.

You can choose any location to define the tasks, and whatever name you like for the global poe alias.

.. warning::

  For this to work Poe the Poet must be installed globally such as via pipx or homebrew.


Shell completions for global tasks
----------------------------------

If you uze zsh or fish then the usual completion script should just work with your alias (as long as it was created with poethepoet >=0.28.0).

However for bash you'll need to generate a new completion script for the alias specifying the alias and the path to you global tasks like so:

.. code-block:: bash

  # System bash
  poe _bash_completion edgar ~/.poethepoet > /etc/bash_completion.d/edgar.bash-completion

  # Homebrew bash
  poe _bash_completion edgar ~/.poethepoet > $(brew --prefix)/etc/bash_completion.d/edgar.bash-completion

.. note::

  These examples assume your global poe alias is ``edgar``, and your global tasks live at ``~/.poethepoet``.

How to ensure installed bash completions are enabled may vary depending on your system.


