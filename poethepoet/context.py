from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from .config import PoeConfig
    from .env.manager import EnvVarsManager
    from .executor import PoeExecutor
    from .ui import PoeUi


from typing import Protocol


class ContextProtocol(Protocol):
    config: PoeConfig
    exec_cache: dict[str, Any]
    ui: PoeUi | None

    def save_task_output(self, invocation: tuple[str, ...], captured_stdout: bytes):
        ...

    def has_task_output(self, invocation: tuple[str, ...]) -> bool:
        ...

    def get_task_output(self, invocation: tuple[str, ...]) -> str:
        ...

    def get_executor(
        self,
        invocation: tuple[str, ...],
        env: EnvVarsManager,
        working_dir: Path,
        *,
        executor_config: Mapping[str, str] | None = None,
        capture_stdout: str | bool = False,
        resolve_python: bool = False,
        delegate_dry_run: bool = False,
    ) -> PoeExecutor:
        ...


class RunContext:
    config: PoeConfig
    exec_cache: dict[str, Any]
    ui: PoeUi | None
    env: EnvVarsManager
    dry: bool
    poe_active: str | None
    multistage: bool = False

    def __init__(
        self,
        config: PoeConfig,
        ui: PoeUi,
        env: Mapping[str, str],
        dry: bool,
        poe_active: str | None,
        multistage: bool = False,
        cwd: Path | str | None = None,
    ):
        from .env.manager import EnvVarsManager

        self.config = config
        self.ui = ui
        self.dry = dry
        self.poe_active = poe_active
        self.multistage = multistage
        self.exec_cache = {}
        self._task_outputs = TaskOutputCache()

        # Init root EnvVarsManager
        self.env = EnvVarsManager(self.config, self.ui, base_env=env, cwd=cwd)
        for config_part in self.config.partitions():
            self.env.apply_env_config(
                envfile=config_part.get("envfile", None),
                config_env=config_part.get("env", None),
                config_dir=config_part.config_dir,
                config_working_dir=config_part.cwd,
            )

    def _get_dep_values(
        self, used_task_invocations: Mapping[str, tuple[str, ...]]
    ) -> dict[str, str]:
        """
        Get env vars from upstream tasks declared via the uses option.
        """
        return {
            var_name: self.get_task_output(invocation)
            for var_name, invocation in used_task_invocations.items()
        }

    def save_task_output(self, invocation: tuple[str, ...], captured_stdout: bytes):
        self._task_outputs.save_task_output(invocation, captured_stdout)

    def has_task_output(self, invocation: tuple[str, ...]) -> bool:
        return self._task_outputs.has_task_output(invocation)

    def get_task_output(self, invocation: tuple[str, ...]) -> str:
        return self._task_outputs.get_task_output(invocation)

    def get_executor(
        self,
        invocation: tuple[str, ...],
        env: EnvVarsManager,
        working_dir: Path,
        *,
        executor_config: Mapping[str, str] | None = None,
        capture_stdout: str | bool = False,
        resolve_python: bool = False,
        delegate_dry_run: bool = False,
    ) -> PoeExecutor:
        """
        Get an Executor object for use with this invocation.

        if delegate_dry_run is set then the task will always be executed and be
        entrusted to not have any side effects when the dry-run flag is set.
        """

        from .executor import PoeExecutor

        if not executor_config:
            assert self.ui
            if self.ui["executor"]:
                executor_config = {"type": self.ui["executor"]}
            else:
                executor_config = self.config.executor

        return PoeExecutor.get(
            invocation=invocation,
            context=self,
            executor_config=executor_config,
            env=env,
            working_dir=working_dir,
            capture_stdout=capture_stdout,
            resolve_python=resolve_python,
            dry=False if delegate_dry_run else self.dry,
        )


class InitializationContext:
    exec_cache: dict[str, Any]
    ui: PoeUi | None = None

    def __init__(self, config: PoeConfig):
        self._captured_stdout: dict[tuple[str, ...], str] = {}
        self.config = config
        self.exec_cache = {}
        self._task_outputs = TaskOutputCache()

    def save_task_output(self, invocation: tuple[str, ...], captured_stdout: bytes):
        self._task_outputs.save_task_output(invocation, captured_stdout)

    def has_task_output(self, invocation: tuple[str, ...]) -> bool:
        return self._task_outputs.has_task_output(invocation)

    def get_task_output(self, invocation: tuple[str, ...]) -> str:
        return self._task_outputs.get_task_output(invocation)

    def get_executor(
        self,
        invocation: tuple[str, ...],
        env: EnvVarsManager,
        working_dir: Path,
        *,
        executor_config: Mapping[str, str] | None = None,
        capture_stdout: str | bool = False,
        resolve_python: bool = False,
        delegate_dry_run: bool = False,
    ) -> PoeExecutor:
        """
        Get an Executor object for use with this invocation.

        if delegate_dry_run is set then the task will always be executed and be
        entrusted to not have any side effects when the dry-run flag is set.
        """

        from .executor import PoeExecutor

        assert (
            not delegate_dry_run
        ), "delegate_dry_run option not valid on InitializationContext"

        return PoeExecutor.get(
            invocation=invocation,
            context=self,
            executor_config=executor_config or self.config.executor,
            env=env,
            working_dir=working_dir,
            capture_stdout=capture_stdout,
            resolve_python=resolve_python,
            dry=False,
        )


class TaskOutputCache:
    def __init__(self):
        self._captured_stdout: dict[tuple[str, ...], str] = {}

    def save_task_output(self, invocation: tuple[str, ...], captured_stdout: bytes):
        """
        Store the stdout data from a task so that it can be reused by other tasks
        """
        try:
            self._captured_stdout[invocation] = captured_stdout.decode()
        except UnicodeDecodeError:
            # Attempt to recover in case a specific encoding is configured
            if io_encoding := os.environ.get("PYTHONIOENCODING"):
                self._captured_stdout[invocation] = captured_stdout.decode(io_encoding)
            else:
                raise

    def has_task_output(self, invocation: tuple[str, ...]) -> bool:
        """
        Check whether there exists stored output for this invocation
        """
        return invocation in self._captured_stdout

    def get_task_output(self, invocation: tuple[str, ...]) -> str:
        """
        Get the stored stdout data from a task so that it can be reused by other tasks

        New lines are replaced with whitespace similar to how unquoted command
        interpolation works in bash.
        """
        return re.sub(r"\s+", " ", self._captured_stdout[invocation].strip("\r\n"))
