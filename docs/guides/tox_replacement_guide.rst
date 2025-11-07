Replacing Tox with UV and Poe
==============================

This guide shows you how to replace `tox <https://tox.wiki/>`_ with Poe the Poet and `uv <https://docs.astral.sh/uv/>`_ for running tests across multiple Python versions and environments.

Why Replace Tox?
----------------

While tox is a powerful tool for test automation, using Poe the Poet with uv offers several advantages:

- **Faster execution**: uv is significantly faster than traditional virtualenv tools
- **Single configuration file**: Everything in ``pyproject.toml``
- **Better integration**: Works seamlessly with your existing poetry or uv workflow
- **More flexible**: Leverage all of Poe's task composition features
- **Simpler syntax**: More intuitive configuration

Prerequisites
-------------

Install both uv and Poe the Poet:

.. code-block:: bash

    # Install uv
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Install Poe the Poet
    pipx install poethepoet

Basic Migration
---------------

A typical ``tox.ini`` file might look like this:

.. code-block:: ini

    [tox]
    envlist = py39,py310,py311,py312

    [testenv]
    deps = pytest
           pytest-cov
    commands = pytest tests --cov=mypackage

Here's the equivalent configuration using Poe the Poet with uv:

.. code-block:: toml

    [tool.poe.executor]
    type = "uv"

    [tool.poe.tasks.test-py39]
    cmd = "pytest tests --cov=mypackage"
    executor_run_options = ["--isolated", "--python", "3.9"]

    [tool.poe.tasks.test-py310]
    cmd = "pytest tests --cov=mypackage"
    executor_run_options = ["--isolated", "--python", "3.10"]

    [tool.poe.tasks.test-py311]
    cmd = "pytest tests --cov=mypackage"
    executor_run_options = ["--isolated", "--python", "3.11"]

    [tool.poe.tasks.test-py312]
    cmd = "pytest tests --cov=mypackage"
    executor_run_options = ["--isolated", "--python", "3.12"]

    [tool.poe.tasks.test-all]
    sequence = ["test-py39", "test-py310", "test-py311", "test-py312"]

Run all tests with:

.. code-block:: bash

    poe test-all

Or run tests for a specific version:

.. code-block:: bash

    poe test-py311

Understanding executor_run_options
-----------------------------------

The ``executor_run_options`` are passed directly to ``uv run``. Common options include:

``--isolated``
    Runs in an isolated environment, preventing access to the global Python packages. This ensures your tests run in a clean environment, similar to tox's default behavior.

``--python <version>``
    Specifies which Python version to use. This is the key to running tests across multiple Python versions.

``--with <package>``
    Adds additional packages to the environment. Useful for optional dependencies or test utilities.

``--no-sync``
    Skips dependency synchronization, which can speed up execution if you know your environment is already set up.

Advanced Configurations
-----------------------

Testing with Different Dependency Sets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you need to test against different versions of dependencies (like tox's factors):

.. code-block:: toml

    [tool.poe.tasks.test-django32]
    cmd = "pytest tests"
    executor_run_options = [
        "--isolated",
        "--python", "3.11",
        "--with", "django==3.2.*"
    ]

    [tool.poe.tasks.test-django42]
    cmd = "pytest tests"
    executor_run_options = [
        "--isolated",
        "--python", "3.11",
        "--with", "django==4.2.*"
    ]

Testing with Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To test optional dependency groups defined in your ``pyproject.toml``:

.. code-block:: toml

    [tool.poe.tasks.test-extras]
    cmd = "pytest tests"
    executor_run_options = [
        "--isolated",
        "--python", "3.11",
        "--extra", "all"
    ]

Pre and Post Test Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use sequence tasks to run commands before and after tests:

.. code-block:: toml

    [tool.poe.tasks.lint]
    cmd = "ruff check ."

    [tool.poe.tasks.test-py311]
    cmd = "pytest tests --cov=mypackage"
    executor_run_options = ["--isolated", "--python", "3.11"]

    [tool.poe.tasks.coverage-report]
    cmd = "coverage report"

    [tool.poe.tasks.ci]
    sequence = ["lint", "test-py311", "coverage-report"]

Parallel Execution
~~~~~~~~~~~~~~~~~~

Unlike tox's ``-p`` flag, Poe doesn't currently support parallel task execution out of the box. However, you can use shell tasks to achieve this:

.. code-block:: toml

    [tool.poe.tasks.test-parallel]
    shell = """
    poe test-py39 &
    poe test-py310 &
    poe test-py311 &
    poe test-py312 &
    wait
    """

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

Set environment variables for specific test runs:

.. code-block:: toml

    [tool.poe.tasks.test-integration]
    cmd = "pytest tests/integration"
    executor_run_options = ["--isolated", "--python", "3.11"]
    env = { DATABASE_URL = "postgresql://localhost/test_db" }

Migration Checklist
-------------------

When migrating from tox to Poe + uv, consider these steps:

1. Install uv and Poe the Poet
2. Set up the uv executor in your ``pyproject.toml``
3. Create a task for each Python version you want to test
4. Add a ``test-all`` sequence task to run all version tests
5. Migrate any ``setenv`` configurations to task-level ``env`` options
6. Convert ``commands_pre`` to sequence task dependencies
7. Update your CI/CD configuration to use ``poe`` instead of ``tox``
8. Remove ``tox.ini`` once everything works

CI/CD Integration
-----------------

GitHub Actions
~~~~~~~~~~~~~~

Replace tox in your GitHub Actions workflow:

.. code-block:: yaml

    name: Tests

    on: [push, pull_request]

    jobs:
      test:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4

          - name: Install uv
            run: curl -LsSf https://astral.sh/uv/install.sh | sh

          - name: Install Poe the Poet
            run: pipx install poethepoet

          - name: Run tests
            run: poe test-all

GitLab CI
~~~~~~~~~

.. code-block:: yaml

    test:
      image: python:3.11
      before_script:
        - curl -LsSf https://astral.sh/uv/install.sh | sh
        - export PATH="$HOME/.cargo/bin:$PATH"
        - pipx install poethepoet
      script:
        - poe test-all

Comparison Table
----------------

Here's a quick comparison of common tox features and their Poe + uv equivalents:

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Feature
     - Tox
     - Poe + uv
   * - Multiple Python versions
     - ``envlist = py39,py310``
     - ``executor_run_options = ["--python", "3.9"]``
   * - Isolated environments
     - Default behavior
     - ``executor_run_options = ["--isolated"]``
   * - Install dependencies
     - ``deps = pytest``
     - Managed by uv from ``pyproject.toml``
   * - Run commands
     - ``commands = pytest``
     - ``cmd = "pytest"``
   * - Environment variables
     - ``setenv = VAR=value``
     - ``env = { VAR = "value" }``
   * - Command sequences
     - ``commands_pre``, ``commands``
     - ``sequence = ["cmd1", "cmd2"]``
   * - Skip install
     - ``skip_install = true``
     - ``executor_run_options = ["--no-sync"]``
   * - Parallel execution
     - ``tox -p``
     - Custom shell script with ``&`` and ``wait``

Common Pitfalls
---------------

Python Version Not Found
~~~~~~~~~~~~~~~~~~~~~~~~

If uv can't find a specific Python version, ensure it's installed on your system:

.. code-block:: bash

    # Install specific Python version with uv
    uv python install 3.11

Dependency Resolution Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you encounter dependency conflicts, ensure your ``pyproject.toml`` dependencies are properly specified. Unlike tox, uv uses your project's actual dependency specification.

Missing Test Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~

Make sure test dependencies are either in your ``pyproject.toml`` or added via ``--with`` options:

.. code-block:: toml

    [tool.poe.tasks.test-py311]
    cmd = "pytest tests"
    executor_run_options = [
        "--isolated",
        "--python", "3.11",
        "--with", "pytest",
        "--with", "pytest-cov"
    ]

Performance Tips
----------------

1. **Use --no-sync for faster reruns**: If you know dependencies haven't changed:

   .. code-block:: toml

       executor_run_options = ["--no-sync", "--python", "3.11"]

2. **Cache uv environments in CI**: Configure your CI to cache ``~/.cache/uv``

3. **Run only changed version tests locally**: Instead of ``poe test-all``, run specific versions during development

Further Reading
---------------

- :ref:`UV Executor run options<UV Executor run options>` - Detailed documentation on executor options
- :doc:`composition_guide` - Learn more about task composition
- `uv documentation <https://docs.astral.sh/uv/>`_ - Learn more about uv options
