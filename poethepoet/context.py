from __future__ import annotations

import asyncio
import os
import re
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, Protocol

from .io import PoeIO
from .shutdown import ShutdownManager

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Mapping
    from pathlib import Path

    from .config import PoeConfig
    from .env.manager import EnvVarsManager
    from .executor import PoeExecutor
    from .ui import PoeUi


class ContextProtocol(Protocol):
    config: PoeConfig
    exec_cache: dict[str, Any]
    ui: PoeUi | None
    enable_output_streaming: bool

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
        io: PoeIO | None = None,
    ) -> PoeExecutor:
        ...


class RunContext:
    config: PoeConfig
    exec_cache: dict[str, Any]
    ui: PoeUi | None
    env: EnvVarsManager
    dry: bool
    poe_active: str | None
    multistage: bool = False  # FIXME: check if this is used anywhere!
    enable_output_streaming: bool = False

    def __init__(
        self,
        config: PoeConfig,
        ui: PoeUi,
        env: Mapping[str, str],
        dry: bool,
        poe_active: str | None,
        multistage: bool = False,
        cwd: Path | str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        from .env.manager import EnvVarsManager

        self.config = config
        self.ui = ui
        self.dry = dry
        self.poe_active = poe_active
        self.multistage = multistage
        self.exec_cache = {}
        self._task_outputs = TaskOutputCache()
        self._loop = loop or asyncio.get_event_loop()
        self._shutdown_manager = ShutdownManager(self._loop, self.ui.io)

        # Init root EnvVarsManager
        self.env = EnvVarsManager(self.config, self.ui.io, base_env=env, cwd=cwd)
        for config_part in self.config.partitions():
            self.env.apply_env_config(
                envfile=config_part.get("envfile", None),
                config_env=config_part.get("env", None),
                config_dir=config_part.config_dir,
                config_working_dir=config_part.cwd,
            )

    def track_async_task(
        self, coro: Any, *, name: str | None = None
    ) -> asyncio.Task[Any]:
        """
        Create a task that is tracked by the shutdown manager
        """
        task = self._loop.create_task(coro, name=name)
        self._shutdown_manager.tasks.add(task)
        return task

    @classmethod
    @asynccontextmanager
    async def scope(
        cls,
        config: PoeConfig,
        ui: PoeUi,
        env: Mapping[str, str],
        dry: bool,
        poe_active: str | None,
        multistage: bool = False,
        cwd: Path | str | None = None,
    ):
        """
        Context manager to create a RunContext for the duration of the context
        """

        context = cls(
            config=config,
            ui=ui,
            env=env,
            dry=dry,
            poe_active=poe_active,
            multistage=multistage,
            cwd=cwd,
            loop=asyncio.get_running_loop(),
        )

        scope_task = asyncio.current_task()
        assert scope_task is not None
        scope_task.set_name("RunContextScope")
        context._shutdown_manager.tasks.add(scope_task)

        try:
            context._shutdown_manager.install_handler()
            yield context
        finally:
            context._shutdown_manager.restore_handler()

    def register_subprocess(self, proc: Process):
        self._shutdown_manager.processes.add(proc)

    def register_async_task(self, task: asyncio.Task[Any]):
        self._shutdown_manager.tasks.add(task)

    @contextmanager
    def output_streaming(self, enabled: bool = True):
        """
        When output streaming is enabled, all otherwise free task output to stdout will
        be captured by the executor, so that the calling task can process it as it
        arrives.

        Yields True if the mode was changed, False otherwise.
        """
        if enabled == self.enable_output_streaming:
            # Reentrant mode
            yield False
            return

        outer_value = self.enable_output_streaming
        self.enable_output_streaming = enabled
        try:
            yield True
        finally:
            self.enable_output_streaming = outer_value

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
        io: PoeIO | None = None,
    ) -> PoeExecutor:
        """
        Get an Executor object for use with this invocation.

        if delegate_dry_run is set then the task will always be executed and be
        entrusted to not have any side effects when the dry-run flag is set.
        """

        from .executor import PoeExecutor

        if not executor_config:
            if self.ui and self.ui["executor"]:
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
            io=io or self.ui.io if self.ui else PoeIO.get_default_io(),
        )


class InitializationContext:
    exec_cache: dict[str, Any]
    ui: PoeUi | None = None
    enable_output_streaming: bool = False

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
        io: PoeIO | None = None,
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
            io=io or self.ui.io if self.ui else PoeIO.get_default_io(),
        )


class TaskOutputCache:
    _captured_stdout: dict[tuple[str, ...], str]

    def __init__(self):
        self._captured_stdout = {}

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
