from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from ..exceptions import ConfigValidationError, ExecutionError, PoeException
from ..options import PoeOptions

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import AsyncIterator, Mapping, MutableMapping, Sequence

    from ..context import ContextProtocol
    from ..env.task_env import TaskEnv
    from ..io import PoeIO

# Once a subprocess has exited, processes it started may still hold its output open,
# so reading its output stops when it goes quiet for OUTPUT_IDLE_TIMEOUT_S, or at the
# latest OUTPUT_DEADLINE_S after the subprocess exited
OUTPUT_IDLE_TIMEOUT_S = 0.25
OUTPUT_DEADLINE_S = 2.5
EXIT_POLL_INTERVAL_S = 0.05


class PoeProcess:
    """
    Wraps asyncio.subprocess.Process with poe-specific metadata for shutdown handling.

    Each subprocess is started in a new process group, so the methods for stopping it
    act on the whole group, reaching any processes it started in turn.
    """

    _is_windows: ClassVar[bool] = sys.platform == "win32"

    def __init__(
        self,
        process: Process,
        *,
        no_console_ctrl: bool = False,
        io: PoeIO | None = None,
    ):
        self._process = process
        self.no_console_ctrl = no_console_ctrl
        self.shutdown_urgency = 0
        self._io = io

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    @property
    def stdout(self) -> asyncio.StreamReader | None:
        return self._process.stdout

    @property
    def stdin(self) -> asyncio.StreamWriter | None:
        return self._process.stdin

    async def wait(self) -> int:
        """
        Wait for the subprocess to exit and return its return code, without waiting
        for any processes it started that may still hold its output open.
        """
        if sys.version_info >= (3, 13):
            return await self._process.wait()

        # Before python 3.13, wait() also waits for the subprocess's pipes to close
        # (see gh-119710), so watch for the return code being set on exit as well
        wait_task = asyncio.ensure_future(self._process.wait())
        try:
            while (returncode := self._process.returncode) is None:
                await asyncio.wait([wait_task], timeout=EXIT_POLL_INTERVAL_S)
            return returncode
        finally:
            wait_task.cancel()

    async def read_output(self, chunk_size: int = 2**16) -> AsyncIterator[bytes]:
        """
        Yield chunks of the subprocess's stdout until it closes, or until it goes
        quiet or reaches the deadline once the subprocess has exited.
        """
        if (stdout := self._process.stdout) is None:
            return

        loop = asyncio.get_running_loop()
        exit_task: asyncio.Future[Any] = asyncio.ensure_future(self.wait())
        read_task: asyncio.Future[bytes] | None = None
        deadline: float | None = None
        try:
            while True:
                # Only one read can be pending at a time, so it's kept across waits
                read_task = read_task or asyncio.ensure_future(stdout.read(chunk_size))
                if deadline is None and exit_task.done():
                    deadline = loop.time() + OUTPUT_DEADLINE_S

                if deadline is None:
                    await asyncio.wait(
                        [read_task, exit_task], return_when=asyncio.FIRST_COMPLETED
                    )
                elif (remaining_s := deadline - loop.time()) > 0:
                    await asyncio.wait(
                        [read_task], timeout=min(OUTPUT_IDLE_TIMEOUT_S, remaining_s)
                    )

                if not read_task.done():
                    if deadline is None:
                        continue  # The subprocess exited, so start the deadline
                    # Quiet for too long, or out of time, since it exited
                    self._close_pipes()
                    return
                if not (chunk := read_task.result()):
                    return
                read_task = None
                yielded_at = loop.time()
                yield chunk
                if deadline is not None:
                    # The deadline only limits waiting for output, so time spent by
                    # the consumer, e.g. writing to a slow terminal, doesn't count
                    deadline += loop.time() - yielded_at
        finally:
            exit_task.cancel()
            if read_task:
                read_task.cancel()

    def _close_pipes(self) -> None:
        """
        Close the pipes of an exited subprocess that are still held open by other
        processes, rather than leave asyncio to close them once its loop has closed.
        """
        if transport := getattr(self._process, "_transport", None):
            transport.close()

    def interrupt(self) -> None:
        """
        Interrupt the process group, as pressing ctrl+c would.
        """
        if not self._is_windows:
            self.signal_group(signal.SIGINT)
        elif self.no_console_ctrl:
            # Processes that can't take console ctrl events are force-terminated
            # instead, to avoid corrupting the console
            self._taskkill(force=True)
        else:
            self._print_debug(
                " ! Sending CTRL_BREAK_EVENT to subprocess group %s", self.pid
            )
            # Delivery can fail, e.g. without a console, in which case escalating to
            # terminate will stop the process instead
            with contextlib.suppress(OSError):
                self._process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]

    def terminate(self) -> None:
        """
        Ask the process group to terminate.
        """
        if self._is_windows:
            self._taskkill(force=False)
        else:
            self.signal_group(signal.SIGTERM)

    def kill(self) -> None:
        """
        Kill the process group.
        """
        if self._is_windows:
            self._taskkill(force=True)
        else:
            self.signal_group(signal.SIGKILL)

    def is_running(self) -> bool:
        """
        Check whether the subprocess is still running, or on POSIX, whether anything
        it left running in its process group is. The group's id can't be reused by a
        new group until every process in it has exited.
        """
        if self._process.returncode is None:
            return True
        if self._is_windows:
            return False
        try:
            os.killpg(self.pid, 0)  # type: ignore[attr-defined]
        except (ProcessLookupError, PermissionError):
            # As for signal_group, macOS refuses with EPERM once all have exited
            return False
        return True

    def signal_group(self, sig: int) -> None:
        """
        Send a POSIX signal to the process group led by this subprocess.
        """
        self._print_debug(
            " ! Sending %s to subprocess group %s", signal.Signals(sig).name, self.pid
        )
        # macOS refuses with EPERM, rather than ESRCH, once every process in the group
        # has exited but not yet been reaped
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(self.pid, sig)  # type: ignore[attr-defined]

    def _taskkill(self, force: bool) -> None:
        self._print_debug(
            " ! %s subprocess tree %s",
            "Force-terminating" if force else "Terminating",
            self.pid,
        )
        subprocess.run(
            ["taskkill", *(["/F"] if force else []), "/T", "/PID", str(self.pid)],
            capture_output=True,
        )

    def _print_debug(self, message: str, *args: Any) -> None:
        if self._io:
            self._io.print_debug(message, *args)


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
        """
        Specifies the executor type. 'auto' uses the most appropriate executor,
        'poetry' uses the poetry environment, 'uv' uses `uv run` to run tasks,
        'virtualenv' specifies a virtual environment, and 'simple' runs tasks
        without any specific environment setup.
        """

    def __init__(
        self,
        invocation: tuple[str, ...],
        context: ContextProtocol,
        options: PoeExecutor.ExecutorOptions,
        env: TaskEnv,
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
        env: TaskEnv,
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

        if executor_type not in cls.__executor_types:
            raise PoeException(f"Cannot instantiate unknown executor {executor_type!r}")
        return cls.__executor_types[executor_type]

    async def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> PoeProcess:
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
    ) -> PoeProcess:
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
                    try:
                        self._exec(cmd, env=env)
                    except FileNotFoundError as error:
                        # execvpe reports the last path it tried rather than cmd[0]
                        await self._handle_file_not_found(cmd, error)

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
        except OSError as error:
            if error.filename == cmd[0]:
                # e.g. the file isn't executable or has no shebang
                raise PoeException(
                    f"executable {cmd[0]!r} could not be run: {error.strerror}"
                ) from error
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
            (self.env.get_subprocess_env_vars() if env is None else env),
            POE_ACTIVE=cast("str", self.__key__),
        )
        if self.working_dir:
            os.chdir(self.working_dir)
        sys.stdout.flush()

        # if running tests then wrap up coverage instrumentation while we still can
        _stop_coverage()

        try:
            os.execvpe(cmd[0], tuple(cmd), exec_env)
        except FileNotFoundError:
            raise
        except OSError as error:
            # execvpe may report the path it resolved rather than cmd[0]
            raise PoeException(
                f"executable {cmd[0]!r} could not be run: {error.strerror}"
            ) from error

    async def _exec_via_subproc(
        self,
        cmd: Sequence[str],
        *,
        input: bytes | None = None,
        env: Mapping[str, str] | None = None,
        shell: bool = False,
    ) -> PoeProcess:
        from subprocess import PIPE

        # Every subprocess leads its own process group, which is signalled to stop it
        popen_kwargs: MutableMapping[str, Any] = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}  # type: ignore[attr-defined]
            if self._is_windows
            else {"start_new_session": True}
        )
        if self.dry:
            # A dry run doesn't execute the command, so we just return a dummy process
            return PoeProcess(
                await asyncio.create_subprocess_exec(
                    sys.executable, "-c", "", **popen_kwargs
                ),
                io=self._io,
            )
        popen_kwargs["env"] = dict(
            (self.env.get_subprocess_env_vars() if env is None else env),
            POE_ACTIVE=self.__key__,
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

        no_console_ctrl = (
            self._is_windows and not shell and cmd[0].lower().endswith((".bat", ".cmd"))
        )
        process = PoeProcess(proc, no_console_ctrl=no_console_ctrl, io=self._io)

        if self.capture_stdout is True:
            captured_stdout = b"".join([chunk async for chunk in process.read_output()])
            self.context.save_task_output(self.invocation, captured_stdout)

        return process

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
    def get_executor_class(cls, key: str) -> type[PoeExecutor]:
        """
        Look up a registered PoeExecutor subclass by its `__key__`.

        Public read-side complement to MetaPoeExecutor's registration logic.
        Raises KeyError if the key isn't registered.

        Note: "auto" is NOT registered as a PoeExecutor subclass — it's a
        meta-option that PoeExecutor.validate_config resolves to one of the
        concrete subclasses at runtime. Callers that need to enumerate
        "every accepted executor type" must add "auto" explicitly.
        """
        if key not in cls.__executor_types:
            raise KeyError(f"Unknown executor type {key!r}")
        return cls.__executor_types[key]

    @classmethod
    def get_executor_types(cls) -> tuple[str, ...]:
        """
        Return all registered executor keys (in registration order).
        Mirrors PoeTask.get_task_types().
        """
        return tuple(cls.__executor_types.keys())

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
            next(cls.__executor_types[executor_type].ExecutorOptions.parse(config))


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
