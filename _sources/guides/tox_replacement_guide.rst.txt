Replacing tox with uv and Poe the Poet
======================================

This guide demonstrates how Poe the Poet and |uv_link| can replace |tox_link| for running tests across multiple python versions and environments.


Why replace tox?
----------------

While tox is a powerful tool for test automation, using Poe the Poet with uv offers comparable expressiveness for many use cases, and several compelling advantages:

- **Faster execution**: uv is significantly faster than traditional virtualenv tools
- **Unified configuration**: everything in ``pyproject.toml``
- **Better integration**: works seamlessly with your existing uv workflow
- **More flexible**: leverage all of Poe the Poet's task composition features
- **Simpler syntax**: more intuitive task oriented configuration


Prerequisites
-------------

Install both uv and Poe the Poet:

.. code-block:: bash

    # Install uv
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Install Poe the Poet
    uv tool install poethepoet

See other installation methods in the `uv installation guide <https://docs.astral.sh/uv/getting-started/installation/>`_ and :ref:`Poe the Poet installation guide<Installation>`.


Basic migration
---------------

A typical ``tox.ini`` file might look like this:

.. code-block:: ini

    [tox]
    envlist = py310,py311,py312,py313

    [testenv]
    deps = pytest
           pytest-cov
    commands = pytest tests --cov=mypackage

Here's the equivalent configuration using Poe the Poet with the :ref:`uv executor <Uv Executor>`:

.. code-block:: toml

    [tool.poe.executor]
    type = "uv" # Use the uv executor for all tasks by default

    [tool.poe.tasks.test-py39]
    cmd = "pytest tests --cov=mypackage"
    executor = {isolated = true, python = "3.9"} # Specify python version, and that we want an isolated env

    [tool.poe.tasks.test-py310]
    cmd = "pytest tests --cov=mypackage"
    executor = {isolated = true, python = "3.10"}

    [tool.poe.tasks.test-py311]
    cmd = "pytest tests --cov=mypackage"
    executor = {isolated = true, python = "3.11"}

    [tool.poe.tasks.test-py312]
    cmd = "pytest tests --cov=mypackage"
    executor = {isolated = true, python = "3.12"}

    [tool.poe.tasks.test-all]
    sequence = ["test-py39", "test-py310", "test-py311", "test-py312"]

Run all tests with:

.. code-block:: bash

    poe test-all

Or run tests for a specific version:

.. code-block:: bash

    poe test-py311

.. tip::

  See the :ref:`uv executor documentation <Uv Executor>` for a full explanation of these and other available executor options.


Advanced configurations
-----------------------

Testing with different dependency sets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you need to test against different versions of dependencies (like tox's factors):

.. code-block:: toml

    [tool.poe.tasks.test-django32]
    cmd = "pytest tests"
    executor = { isolated = true, python = "3.11", group = "dev", with = "django==3.2.*" }

    [tool.poe.tasks.test-django42]
    cmd = "pytest tests"
    executor = { isolated = true, python = "3.11", group = "dev", with = "django==4.2.*" }

Testing with optional dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pick and choose optional or dev dependency groups defined in your ``pyproject.toml``:

.. code-block:: toml

    [tool.poe.tasks.test-with-extras]
    cmd = "pytest tests"
    executor = { extra = "all", group = ["ci", "debug"], no-group = "docs" }

Compose testing with other tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use sequence tasks to run commands before and after tests:

.. code-block:: toml

    [tool.poe.tasks.lint]
    cmd = "ruff check ."

    [tool.poe.tasks.test-py311]
    cmd = "pytest tests --cov=mypackage"
    executor = { isolated = true, python = "3.11" }

    [tool.poe.tasks.coverage-report]
    cmd = "coverage report"

    [tool.poe.tasks.ci]
    sequence = ["lint", "test-py311", "coverage-report"

Or define a DAG of tasks with task ``deps``:

.. code-block:: toml

    [tool.poe.tasks.lint]
    cmd = "ruff check ."

    [tool.poe.tasks.test-py311]
    cmd = "pytest tests --cov=mypackage"
    executor = { isolated = true, python = "3.11" }
    deps = ["lint"]

See the :doc:`guide on task composition<../guides/composition_guide>` for more examples.

Parallel execution
~~~~~~~~~~~~~~~~~~

tox supports running tests in parallel using the ``-p`` option. Poe the Poet lets you define a parallel task that runs all your test variants concurrently:

.. code-block:: toml

    [tool.poe.tasks.test-parallel]
    parallel = ["test-py39", "test-py310", "test-py311", "test-py312"]

Environment variables
~~~~~~~~~~~~~~~~~~~~~

tox allows setting environment variables for test runs using the ``setenv`` option. You can achieve the same with Poe the Poet using the ``env`` or ``envfile`` options.

Set environment variables directly:

.. code-block:: toml

    [tool.poe.tasks.test-integration]
    cmd = "pytest tests/integration"
    executor = { isolated = true, python = "3.11" }
    env = { DATABASE_URL = "postgresql://localhost/test_db" }

Or load an envfile for the task:

.. code-block:: toml

    [tool.poe.tasks.test-integration]
    cmd = "pytest tests/integration"
    executor = { isolated = true, python = "3.11" }
    envfile = ".env.test"


.. |uv_link| raw:: html

   <a href="https://docs.astral.sh/uv/" target="_blank">uv</a>

.. |tox_link| raw:: html

   <a href="https://tox.wiki/" target="_blank">tox</a>
