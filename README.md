# Poe the Poet

<img alt="Poe the Poet" src="./docs/_static/poe_logo_x2000.png" height="200" width="200" align="left"/>

[![PyPI version](https://img.shields.io/pypi/pyversions/poethepoet.svg)](https://pypi.org/project/poethepoet/)
[![PyPI version](https://img.shields.io/pypi/v/poethepoet.svg)](https://pypi.org/project/poethepoet/)
[![PyPI version](https://img.shields.io/pypi/dw/poethepoet.svg)](https://pypi.org/project/poethepoet/)
[![PyPI version](https://img.shields.io/pypi/l/ansicolortags.svg)](https://github.com/nat-n/poethepoet/blob/doc/init-sphinx/LICENSE)

**A batteries included task runner that works well with [poetry](https://python-poetry.org/).**

**[📖 Read the documentation 📖](https://poethepoet.natn.io/)**

<br clear="both"/>

## Features


- ✅ Straight forward [declaration of project tasks in your pyproject.toml](http://127.0.0.1:5500/tasks/index.html)

- ✅ Tasks are run in poetry's virtualenv ([or another env](http://127.0.0.1:5500/index.html#usage-without-poetry) you specify)

- ✅ [Shell completion of task names](http://127.0.0.1:5500/installation.html#shell-completion) (and global options too for zsh)

- ✅ The poe CLI can be used standalone, or as a [plugin for poetry](https://poethepoet.natn.io/poetry_plugin.html)

- ✅ Tasks can be [commands](http://127.0.0.1:5500/tasks/task_types/cmd.html), [shell scripts](http://127.0.0.1:5500/tasks/task_types/shell.html), [python expressions](http://127.0.0.1:5500/tasks/task_types/expr.html), or references to [python functions](http://127.0.0.1:5500/tasks/task_types/script.html)

- ✅ Concise commands with extra arguments passed to the task `poe [options] task [task_args]`

- ✅ Easily [define CLI arguments](http://127.0.0.1:5500/guides/args_guide.html) for your tasks

- ✅ Tasks can specify and [reference environment variables](http://127.0.0.1:5500/tasks/task_types/cmd.html#ref-env-vars), even without a shell

- ✅ Tasks are [self documenting](http://127.0.0.1:5500/guides/help_guide.html), with optional help messages (just run `poe` with no arguments)

- ✅ Tasks can be composed into [sequences](http://127.0.0.1:5500/guides/composition_guide.html#composing-tasks-into-sequences) or [DAGs](http://127.0.0.1:5500/guides/composition_guide.html#composing-tasks-into-graphs)

- ✅ Works with [`.env` files](http://127.0.0.1:5500/tasks/options.html#loading-environment-variables-from-an-env-file)

- ✅ Can be [used as a library](http://127.0.0.1:5500/guides/library_guide.html) to embed in other tools


## Quick start

1. Install the Poe the Poet via [pipx](https://pypa.github.io/pipx/) or [another method](https://poethepoet.natn.io/installation.html).

  ```sh
  pipx install poethepoet
  ```

2. Define some tasks in your **pyproject.toml**

  ```toml
  [tool.poe.tasks]
  test         = "pytest --cov=my_app"                         # a simple command task
  serve.script = "my_app.service:run(debug=True)"              # python script based task
  tunnel.shell = "ssh -N -L 0.0.0.0:8080:$PROD:8080 $PROD &"   # (posix) shell based task
  ```

3. Run your tasks via the CLI

  ```sh
  $ poe test -v tests/unit # extra CLI arguments are appended to the underlying command
  Poe => pytest --cov=my_app
  ...
  ```

If you're using poetry, then poe will automatically use CLI tools and libraries from your poetry managed virtualenv without you having to run `poetry run` or `poetry shell`

Poe can also be [used without poetry](https://poethepoet.natn.io/index.html#usage-without-poetry).

## Contributing

There's plenty to do, come say hi in the [discussions](https://github.com/nat-n/poethepoet/discussions) or [open an issue](https://github.com/nat-n/poethepoet/issues)! 👋

Also check out the [CONTRIBUTING guide](https://github.com/nat-n/poethepoet/blob/main/.github/CONTRIBUTING.rst) 🤓


## License

[MIT](https://github.com/nat-n/poethepoet/blob/main/LICENSE)
