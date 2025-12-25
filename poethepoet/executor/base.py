from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from ..options import PoeOptions

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Mapping, MutableMapping, Sequence

    from ..context import ContextProtocol
    from ..env.manager import EnvVarsManager
    from ..io import PoeIO


class MetaPoeExecutor(type):
    """
    This metaclass makes all descendants of PoeExecutor (task types) register themselves
    on declaration and validates that they include the expected class attributes.
    """

    def __init__(cls, *args):
        super().__init__(*args)
        if cls.__name__ == "PoeExecutor":
            return
        assert isinstance(getattr(cls, "__key__", None), str)
        assert issubclass(getattr(cls, "ExecutorOptions", None), PoeOptions)
        PoeExecutor._PoeExecutor__executor_types[cls.__key__] = cls


class PoeExecutor(metaclass=MetaPoeExecutor):
    """
    A base class for poe task executors
    """

    working_dir: Path | None

    __executor_types: ClassVar[dict[str, type[PoeExecutor]]] = {}
    __key__: ClassVar[str | None] = None

    class ExecutorOptions(PoeOptions):
        type: str

    def __init__(
        self,
        invocation: tuple[str, ...],
        context: ContextProtocol,
        options: PoeExecutor.ExecutorOptions,
        env: EnvVarsManager,
        *,
        project_dir: Path | None = None,
        working_dir: Path | None = None,
        capture_stdout: str | bool = False,
        resolve_python: bool = False,
        dry: bool = False,
        io: PoeIO,
    ):
        self.invocation = invocation
        self.context = context
        self.options = options
        self.working_dir = working_dir.resolve() if working_dir else None
        self.env = env
        self.capture_stdout = (
            Path(project_dir or self.working_dir or ".").joinpath(
                self.env.fill_template(capture_stdout)
            )
            if capture_stdout and isinstance(capture_stdout, str)
            else bool(capture_stdout)
        )
        self._should_resolve_python = resolve_python
        self.dry = dry
        self._is_windows = sys.platform == "win32"
        self._io = io
        io.print_debug(f" . Initializing {self.__class__.__name__}")

    @classmethod
    def works_with_context(cls, context: ContextProtocol) -> bool:
        return True

    @classmethod
    def get(
        cls,
        invocation: tuple[str, ...],
        context: ContextProtocol,
        executor_config: Mapping[str, str | bool | list[str | bool]],
        env: EnvVarsManager,
        *,
        working_dir: Path | None = None,
        capture_stdout: str | bool = False,
        resolve_python: bool = False,
        dry: bool = False,
        io: PoeIO,
    ) -> PoeExecutor:
        """
        Create an executor.
        """
        executor_cls = cls.resolve_implementation(context, str(executor_config["type"]))
        try:
            executor_options = next(executor_cls.ExecutorOptions.parse(executor_config))
        except ConfigValidationError as error:
            raise ConfigValidationError(
                f"Couldn't parse executor options with executor type "
                f"{executor_config.get('type')!r}"
            ) from error

        return executor_cls(
            invocation=invocation,
            context=context,
            options=executor_options,  # type: ignore[arg-type]
            env=env,
            project_dir=context.config.project_dir,
            working_dir=working_dir,
            capture_stdout=capture_stdout,
            resolve_python=resolve_python,
            dry=dry,
            io=io,
        )

    @classmethod
    def resolve_implementation(cls, context: ContextProtocol, executor_type: str):
        """
        Resolve to an executor class, either as specified in the available config or
        by making some reasonable assumptions based on visible features of the
        environment
        """

        if executor_type == "auto":
            for impl in [
                cls.__executor_types["poetry"],
                cls.__executor_types["uv"],
                cls.__executor_types["virtualenv"],
            ]:
                if impl.works_with_context(context):
                    return impl

            # Fallback to not using any particular environment
            return cls.__executor_types["simple"]

        else:
            if executor_type not in cls.__executor_types:
                raise PoeException(
                    f"Cannot instantiate unknown executor {executor_type!r}"
                )
            return cls.__executor_types[executor_type]

    async def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> Process:
        """
        Execute the given cmd.
        """

        cmd = (*self._resolve_executable(cmd[0]), *cmd[1:])
        return await self._execute_cmd(cmd, input=input, use_exec=use_exec)

    async def _execute_cmd(
        self,
        cmd: Sequence[str],
        *,
        input: bytes | None = None,
        env: Mapping[str, str] | None = None,
        shell: bool = False,
        use_exec: bool = False,
    ) -> Process:
        """
        Execute the given cmd either as a subprocess or use exec to replace the current
        process. Using exec supports fewer options, and doesn't work on windows.
        """

        try:
            if self.working_dir and not self.working_dir.is_dir():
                raise PoeException(
                    f"Working directory {self.working_dir} could not be found."
                )
            if use_exec:
                if input:
                    raise ExecutionError("Cannot exec task that requires input!")
                if shell:
                    raise ExecutionError("Cannot exec task that requires shell!")
                if not self._is_windows:
                    # execvpe doesn't work properly on windows so we just don't go there
                    self._exec(cmd, env=env)

            return await self._exec_via_subproc(cmd, input=input, env=env, shell=shell)
        except FileNotFoundError as error:
            if error.filename == cmd[0]:
                await self._handle_file_not_found(cmd, error)
                # unreachable due to raise in _handle_file_not_found
            if error.filename == self.working_dir:
                raise PoeException(
                    "The specified working directory does not exist "
                    f"'{self.working_dir}'"
                )
            raise

    async def _handle_file_not_found(
        self, cmd: Sequence[str], error: FileNotFoundError
    ):
        raise PoeException(f"executable {cmd[0]!r} could not be found") from error

    def _exec(
        self,
        cmd: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ):
        if self.dry:
            return

        # Beware: this is the point of no return!

        exec_env = dict(
            (self.env.to_dict() if env is None else env), POE_ACTIVE=self.__key__
        )
        if self.working_dir:
            os.chdir(self.working_dir)
        sys.stdout.flush()

        # if running tests then wrap up coverage instrumentation while we still can
        _stop_coverage()

        os.execvpe(cmd[0], tuple(cmd), exec_env)

    async def _exec_via_subproc(
        self,
        cmd: Sequence[str],
        *,
        input: bytes | None = None,
        env: Mapping[str, str] | None = None,
        shell: bool = False,
    ) -> Process:
        from subprocess import PIPE

        if self.dry:
            # A dry run doesn't execute the command, so we just return a dummy process
            return await asyncio.create_subprocess_exec(sys.executable, "-c", "")
        popen_kwargs: MutableMapping[str, Any] = {}
        popen_kwargs["env"] = dict(
            (self.env.to_dict() if env is None else env), POE_ACTIVE=self.__key__
        )
        if input is not None:
            popen_kwargs["stdin"] = PIPE
        if self.capture_stdout or self.context.enable_output_streaming:
            if isinstance(self.capture_stdout, Path):
                if str(self.capture_stdout) in ("/dev/null", "NUL", "D:\\dev\\null"):
                    popen_kwargs["stdout"] = subprocess.DEVNULL
                else:
                    # ruff: noqa: SIM115, ASYNC230
                    popen_kwargs["stdout"] = open(self.capture_stdout, "wb")
            else:
                popen_kwargs["stdout"] = PIPE

            if "PYTHONIOENCODING" not in popen_kwargs["env"]:
                popen_kwargs["env"]["PYTHONIOENCODING"] = "utf-8"

        if self.working_dir is not None:
            popen_kwargs["cwd"] = self.working_dir

        if self._is_windows:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            popen_kwargs["start_new_session"] = True

        # TODO: exclude the subprocess from coverage more gracefully
        _stop_coverage()

        if shell:
            proc = await asyncio.create_subprocess_shell("".join(cmd), **popen_kwargs)
        else:
            proc = await asyncio.create_subprocess_exec(*cmd, **popen_kwargs)

        if input is not None:
            # TODO: Track the write task so we can cancel it if needed, and prevent GC
            #       from cleaning it up too early
            asyncio.create_task(self._pass_input_to_proc(proc, input))  # noqa: RUF006

        if self.capture_stdout is True:
            captured_stdout = await proc.stdout.read() if proc.stdout else b""
            self.context.save_task_output(self.invocation, captured_stdout)

        return proc

    async def _pass_input_to_proc(self, proc: Process, input: bytes):
        if not proc.stdin:
            return
        try:
            proc.stdin.write(input)
            await proc.stdin.drain()
        except Exception:
            pass
        finally:
            try:
                proc.stdin.close()
                await proc.stdin.wait_closed()
            except Exception as error:
                self._io.print_warning(
                    f"Exception while closing stdin for {proc.pid}: {error}"
                )

    def _resolve_executable(self, executable: str):
        if self._should_resolve_python and executable == "python":
            if python := shutil.which("python"):
                yield python
            elif python3 := shutil.which("python3"):
                yield python3
            else:
                self._io.print_debug(
                    " ! Could not resolve python or python3 from the path, "
                    "falling back to sys.executable"
                )
                yield sys.executable

            if self.context.enable_output_streaming and not isinstance(
                self.capture_stdout, Path
            ):
                # Force python subprocesses to be unbuffered mode
                yield "-u"
        else:
            # Attempt to explicitly resolve the target executable, because we can't
            # count on the OS to do this consistently.
            yield shutil.which(executable) or executable

    @classmethod
    def validate_config(cls, config: dict[str, Any]):
        if "type" not in config:
            raise ConfigValidationError(
                "Missing required key 'type' from executor option",
                global_option="executor",
            )

        executor_type = config["type"]
        if executor_type == "auto":
            extra_options = set(config.keys()) - {"type"}
            if extra_options:
                raise ConfigValidationError(
                    f"Unexpected keys for executor config: {extra_options!r}",
                    global_option="executor",
                )

        elif executor_type not in cls.__executor_types:
            raise ConfigValidationError(
                f"Unknown executor type: {executor_type!r}",
                global_option="executor.type",
            )

        else:
            cls.__executor_types[executor_type].ExecutorOptions.parse(config)


def _stop_coverage():
    """
    Running coverage around subprocesses seems to be problematic, esp. on windows.
    There's probably a more elegant solution that this.
    """
    if "coverage" in sys.modules:
        # If Coverage is running then it ends here
        from coverage import Coverage

        cov = Coverage.current()
        if cov:
            cov.stop()
            cov.save()
