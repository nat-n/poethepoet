# Poe the Poet

[![PyPI version](https://img.shields.io/pypi/v/poethepoet.svg)](https://pypi.org/project/poethepoet/)

<img alt="Poe the Poet" src="./docs/_static/poe_logo_x2000.png" height="300" width="300"/>

A task runner that works well with poetry.

## Features

- ✅ Straight forward declaration of project tasks in your pyproject.toml (kind of like npm scripts)

- ✅ Task are run in poetry's virtualenv (or another env you specify)

- ✅ Shell completion of task names (and global options too for zsh)

- ✅ Can be used standalone or as a poetry plugin

- ✅ Tasks can be commands (with or without a shell) or references to python functions (like tool.poetry.scripts)

- ✅ Short and sweet commands with extra arguments passed to the task :bash:`poe [options] task [task_args]`, or you can define arguments explicitly.

- ✅ Tasks can specify and reference environment variables as if they were evaluated by a shell

- ✅ Tasks are self documenting, with optional help messages (just run poe without arguments)

- ✅ Tasks can be defined as a sequence of other tasks

- ✅ Works with .env files

## Getting started

Follow the [installation instructions](https://nat-n.github.io/poethepoet/getting_started/installation.html) in the documentation.


## Basic usage

Follow the [our guides](https://nat-n.github.io/poethepoet/getting_started/basic_usage.html) in the documentation.


## Documentation

Extensive documentation is available at [nat-n.github.io/poethepoet](https://nat-n.github.io/poethepoet)
