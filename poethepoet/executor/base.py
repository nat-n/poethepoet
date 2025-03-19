from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from ..exceptions import ConfigValidationError, ExecutionError, PoeException

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping, Sequence

    from ..context import ContextProtocol
    from ..env.manager import EnvVarsManager


# TODO: maybe invert the control so the executor is given a task to run?

POE_DEBUG = os.environ.get("POE_DEBUG", "0") == "1"


class MetaPoeExecutor(type):
    """
    This metaclass makes all descendents of PoeExecutor (task types) register themselves
    on declaration and validates that they include the expected class attributes.
    """

    def __init__(cls, *args):
        super().__init__(*args)
        if cls.__name__ == "PoeExecutor":
            return
        assert isinstance(getattr(cls, "__key__", None), str)
        assert isinstance(getattr(cls, "__options__", None), dict)
        PoeExecutor._PoeExecutor__executor_types[cls.__key__] = cls


class PoeExecutor(metaclass=MetaPoeExecutor):
    """
    A base class for poe task executors
    """

    working_dir: Path | None

    __executor_types: ClassVar[dict[str, type[PoeExecutor]]] = {}
    __key__: ClassVar[str | None] = None

    def __init__(
        self,
        invocation: tuple[str, ...],
        context: ContextProtocol,
        options: Mapping[str, str],
        env: EnvVarsManager,
        *,
        project_dir: Path | None = None,
        working_dir: Path | None = None,
        capture_stdout: str | bool = False,
        resolve_python: bool = False,
        dry: bool = False,
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

        if POE_DEBUG:
            print(f" . Initializing {self.__class__.__name__}")

    @classmethod
    def works_with_context(cls, context: ContextProtocol) -> bool:
        return True

    @classmethod
    def get(
        cls,
        invocation: tuple[str, ...],
        context: ContextProtocol,
        executor_config: Mapping[str, str],
        env: EnvVarsManager,
        working_dir: Path | None = None,
        capture_stdout: str | bool = False,
        resolve_python: bool = False,
        dry: bool = False,
    ) -> PoeExecutor:
        """
        Create an executor.
        """
        return cls._resolve_implementation(context, executor_config["type"])(
            invocation=invocation,
            context=context,
            options=executor_config,
            env=env,
            project_dir=context.config.project_dir,
            working_dir=working_dir,
            capture_stdout=capture_stdout,
            resolve_python=resolve_python,
            dry=dry,
        )

    @classmethod
    def _resolve_implementation(cls, context: ContextProtocol, executor_type: str):
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

    def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> int:
        """
        Execute the given cmd.
        """

        cmd = (self._resolve_executable(cmd[0]), *cmd[1:])
        return self._execute_cmd(cmd, input=input, use_exec=use_exec)

    def _execute_cmd(
        self,
        cmd: Sequence[str],
        *,
        input: bytes | None = None,
        env: Mapping[str, str] | None = None,
        shell: bool = False,
        use_exec: bool = False,
    ) -> int:
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
                    return self._exec(cmd, env=env)

            return self._exec_via_subproc(cmd, input=input, env=env, shell=shell)
        except FileNotFoundError as error:
            if error.filename == cmd[0]:
                return self._handle_file_not_found(cmd, error)
            if error.filename == self.working_dir:
                raise PoeException(
                    "The specified working directory does not exist "
                    f"'{self.working_dir}'"
                )
            raise

    def _handle_file_not_found(
        self, cmd: Sequence[str], error: FileNotFoundError
    ) -> int:
        raise PoeException(f"executable {cmd[0]!r} could not be found") from error

    def _exec(
        self,
        cmd: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ):
        if self.dry:
            return 0

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

    def _exec_via_subproc(
        self,
        cmd: Sequence[str],
        *,
        input: bytes | None = None,
        env: Mapping[str, str] | None = None,
        shell: bool = False,
    ) -> int:
        import signal
        from subprocess import PIPE, Popen

        if self.dry:
            return 0
        popen_kwargs: MutableMapping[str, Any] = {"shell": shell}
        popen_kwargs["env"] = dict(
            (self.env.to_dict() if env is None else env), POE_ACTIVE=self.__key__
        )
        if input is not None:
            popen_kwargs["stdin"] = PIPE
        if self.capture_stdout:
            if isinstance(self.capture_stdout, Path):
                # ruff: noqa: SIM115
                popen_kwargs["stdout"] = open(self.capture_stdout, "wb")
            else:
                popen_kwargs["stdout"] = PIPE

            if "PYTHONIOENCODING" not in popen_kwargs["env"]:
                popen_kwargs["env"]["PYTHONIOENCODING"] = "utf-8"

        if self.working_dir is not None:
            popen_kwargs["cwd"] = self.working_dir

        # TODO: exclude the subprocess from coverage more gracefully
        _stop_coverage()

        proc = Popen(cmd, **popen_kwargs)

        # signal pass through
        def handle_sigint(signum, _frame):
            # sigint is not handled on windows
            signum = signal.CTRL_C_EVENT if self._is_windows else signum
            proc.send_signal(signum)

        old_sigint_handler = signal.signal(signal.SIGINT, handle_sigint)

        # send data to the subprocess and wait for it to finish
        (captured_stdout, _) = proc.communicate(input)

        if self.capture_stdout is True:
            self.context.save_task_output(self.invocation, captured_stdout)

        # restore signal handler
        signal.signal(signal.SIGINT, old_sigint_handler)

        return proc.returncode

    def _resolve_executable(self, executable: str):
        if self._should_resolve_python and executable == "python":
            if python := shutil.which("python"):
                return python
            if python := shutil.which("python3"):
                return python
            if POE_DEBUG:
                print(
                    " ! Could not resolve python or python3 from the path, "
                    "falling back to sys.executable"
                )
            return sys.executable

        # Attempt to explicitly resolve the target executable, because we can't
        # count on the OS to do this consistently.
        return shutil.which(executable) or executable

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
            cls.__executor_types[executor_type].validate_executor_config(config)

    @classmethod
    def validate_executor_config(cls, config: dict[str, Any]):
        """To be overridden by subclasses if they accept options"""
        extra_options = set(config.keys()) - {"type"}
        if extra_options:
            raise ConfigValidationError(
                f"Unexpected keys for executor config: {extra_options!r}",
                global_option="executor",
            )


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
