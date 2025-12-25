# Poe the Poet

<img alt="Poe the Poet" src="https://raw.githubusercontent.com/nat-n/poethepoet/main/docs/_static/poe_logo_x2000.png" height="200" width="200" align="left"/>

[![Python versions](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.13-blue)](https://pypi.org/project/poethepoet/)
[![PyPI version](https://img.shields.io/pypi/v/poethepoet.svg)](https://pypi.org/project/poethepoet/)
[![Download stats](https://img.shields.io/pypi/dm/poethepoet.svg)](https://pypistats.org/packages/poethepoet)
[![License](https://img.shields.io/pypi/l/ansicolortags.svg)](https://github.com/nat-n/poethepoet/blob/doc/init-sphinx/LICENSE)

**A batteries included task runner that works well with [poetry](https://python-poetry.org/) or [uv](https://docs.astral.sh/uv/).**

**[📖 Read the documentation 📖](https://poethepoet.natn.io/)**

<br clear="both"/>

## Features

- ✅ Straight forward [declaration of project tasks in your pyproject.toml](https://poethepoet.natn.io/tasks/index.html) (or [poe_tasks.toml](https://poethepoet.natn.io/guides/without_poetry.html#usage-without-pyproject-toml))

- ✅ Tasks are run in poetry or uv's virtualenv ([or another env](https://poethepoet.natn.io/index.html#usage-without-poetry) you specify)

- ✅ [Shell completion of task names](https://poethepoet.natn.io/installation.html#shell-completion) (and global options too for zsh)

- ✅ The poe CLI can be used standalone, or as a [plugin for poetry](https://poethepoet.natn.io/poetry_plugin.html)

- ✅ Tasks can be [commands](https://poethepoet.natn.io/tasks/task_types/cmd.html), [shell scripts](https://poethepoet.natn.io/tasks/task_types/shell.html), [python expressions](https://poethepoet.natn.io/tasks/task_types/expr.html), or references to [python functions](https://poethepoet.natn.io/tasks/task_types/script.html)

- ✅ Concise commands with extra arguments passed to the task `poe [options] task [task_args]`

- ✅ Easily [declare named CLI arguments](https://poethepoet.natn.io/guides/args_guide.html) for your tasks

- ✅ Tasks can specify and [reference environment variables](https://poethepoet.natn.io/tasks/task_types/cmd.html#ref-env-vars), even without a shell

- ✅ Tasks are [self documenting](https://poethepoet.natn.io/guides/help_guide.html), with optional help messages (just run `poe` with no arguments)

- ✅ Tasks can be composed to run in [sequence](https://poethepoet.natn.io/guides/composition_guide.html#composing-tasks-into-sequences), in [parallel](https://poethepoet.natn.io/guides/composition_guide.html#composing-tasks-to-run-in-parallel), or as a [DAG](https://poethepoet.natn.io/guides/composition_guide.html#composing-tasks-into-graphs).

- ✅ Works with [`.env` files](https://poethepoet.natn.io/tasks/options.html#loading-environment-variables-from-an-env-file)

- ✅ Can be [used as a library](https://poethepoet.natn.io/guides/library_guide.html) to embed in other tools

- ✅ Tasks can be [defined in python packages](https://poethepoet.natn.io/guides/packaged_tasks.html) for ease of reuse across projects

- ✅ Also works fine as a [general purpose task runner](https://poethepoet.natn.io/guides/without_poetry.html)


## Quick start

1. Install the Poe the Poet globally via [pipx](https://pypa.github.io/pipx/) or [another method](https://poethepoet.natn.io/installation.html).

  ```sh
  pipx install poethepoet
  ```

  Or add it as a poetry project plugin:

  ```toml
  [tool.poetry.requires-plugins]
  poethepoet = ">=0.39"
  ```

2. Define some tasks in your **pyproject.toml**

  ```toml
  [tool.poe.tasks]
  test         = "pytest --cov=my_app"                         # a simple command task
  serve.script = "my_app.service:run(debug=True)"              # python script based task
  tunnel.shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &"   # (posix) shell based task

  # A more complete example with documentation and named arguments
  [tool.poe.tasks.count-incomplete]
  help = "Count incomplete tasks in DynamoDB"
  cmd  = """
  aws dynamodb scan --table-name tasks
                    --select "COUNT"
                    --filter-expression "status >= :status"
                    --expression-attribute-values '{":status":{"S":"incomplete"}}'
                    --no-cli-pager
  """
  args = [
    # Allow $AWS_REGION to be overridden with a CLI option when calling the task
    {name = "AWS_REGION", options = ["--region", "-r"], default = "${AWS_REGION}"}
  ]
  ```

3. Run your tasks via the CLI

  ```sh
  $ poe test -v tests/unit # extra CLI arguments are appended to the underlying command
  Poe => pytest --cov=my_app
  ...
  ```

If you're using poetry or uv, then poe will automatically use CLI tools and libraries from your project's virtualenv without you having to run `poetry run` / `uv run`

Poe can also be [used as a general purpose task runner](https://poethepoet.natn.io/guides/without_poetry.html).

## Contributing

There's plenty to do, come say hi in the [discussions](https://github.com/nat-n/poethepoet/discussions) or [open an issue](https://github.com/nat-n/poethepoet/issues)! 👋

Also check out the [CONTRIBUTING guide](https://github.com/nat-n/poethepoet/blob/main/.github/CONTRIBUTING.rst) 🤓


## License

[MIT](https://github.com/nat-n/poethepoet/blob/main/LICENSE)
