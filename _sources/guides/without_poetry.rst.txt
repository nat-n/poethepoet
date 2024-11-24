Usage without poetry
====================

Poe the Poet was originally intended as the missing task runner for |poetry_link|. But it works just as well with any other kind of virtualenv, or simply as a general purpose way to define handy tasks for use within a certain directory structure! This behaviour is configurable via the :ref:`tool.poe.executor global option<Change the executor type>`.

By default poe will run tasks in the poetry managed virtual environment, if the pyproject.toml contains a :toml:`tool.poetry` section. If it doesn't then poe looks for a virtualenv to use at ``./.venv`` or ``./venv`` relative to the pyproject.toml.

If no virtualenv is found then poe will run tasks without any special environment management.


Usage with uv
-------------

|uv_link| is another popular tool for managing project dependencies with a pyproject.toml file. Since uv works by keeping a virtual environment inside the project directory at ``./.venv`` poethepoet will automatically discover and use uv project dependencies, just like with poetry.

So Poe the Poet also works well with uv.


Usage without pyproject.toml
----------------------------

When using Poe the Poet outside of a poetry (or other |pep518_link|) project, you can avoid the potential confusion of creating a `pyproject.toml` file and instead name the file ``poe_tasks.toml``.


Usage with with json or yaml instead of toml
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As an alternative to toml, poethepoet configuration can also be provided via yaml or json files. When searching for a tasks file to load within a certain directory poe will try the following file names in order:

- pyproject.toml
- poe_tasks.toml
- poe_tasks.yaml
- poe_tasks.json

If `pyproject.toml` exists but does not contain the key prefix ``tool.poe`` then the search continues with `poe_tasks.toml`. If one of the listed ``poe_tasks.*`` files exist then the search is terminated, even if the file is empty.

When config is loaded from a file other than `pyproject.toml` the ``tool.poe`` namespace for poe config is optional. So for example the following two poe_tasks.yaml files are equivalent and both valid:

.. code-block:: yaml
  :caption: poe_tasks.yaml

  env:
    VAR0: FOO

  tasks:
    show-vars:
      cmd: "echo $VAR0 $VAR1 $VAR2"
      env:
        VAR1: BAR
      args:
        - name: VAR2
          options: ["--var"]
          default: BAZ

.. code-block:: yaml
  :caption: poe_tasks.yaml

  tool:
    poe:
      env:
        VAR0: FOO

      tasks:
        show-vars:
          cmd: "echo $VAR0 $VAR1 $VAR2"
          env:
            VAR1: BAR
          args:
            - name: VAR2
              options: ["--var"]
              default: BAZ

.. |uv_link| raw:: html

   <a href="https://docs.astral.sh/uv/" target="_blank">uv</a>

.. |poetry_link| raw:: html

   <a href="https://python-poetry.org/" target="_blank">poetry</a>

.. |pep518_link| raw:: html

   <a href="https://peps.python.org/pep-0518/" target="_blank">PEP 518</a>
