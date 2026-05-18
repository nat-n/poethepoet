from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from ..options.annotations import Metadata
from .base import PoeExecutor

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..context import ContextProtocol
    from .base import PoeProcess


class UvExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside a uv managed dev
    environment
    """

    __key__ = "uv"

    class ExecutorOptions(PoeExecutor.ExecutorOptions):
        extra: str | list[str] | None = None
        """
        Include optional dependencies from the specified extra name.
        """

        group: str | list[str] | None = None
        """
        Include dependencies from the specified dependency group.
        """

        no_group: Annotated[
            str | list[str] | None, Metadata(config_name="no-group")
        ] = None
        """
        Disable the specified dependency group.
        """

        with_: Annotated[str | list[str] | None, Metadata(config_name="with")] = None
        """
        Run with the given packages installed.
        """

        isolated: bool = False
        """
        Run the command in an isolated virtual environment.
        """

        exact: bool = False
        """
        Perform an exact sync, removing extraneous packages from the environment.
        """

        no_sync: Annotated[bool, Metadata(config_name="no-sync")] = False
        """
        Avoid syncing the virtual environment.
        """

        locked: bool = False
        """
        Assert that the uv.lock file is up to date; fail if it would need to be
        updated.
        """

        frozen: bool = False
        """
        Run without updating the uv.lock file.
        """

        no_project: Annotated[bool, Metadata(config_name="no-project")] = False
        """
        Avoid discovering the project or workspace.
        """

        python: str | None = None
        """
        The Python interpreter to use for the run environment.
        """

    __uv_cli_options = ("extra", "group", "no-group", "with", "python")
    __uv_cli_flags = ("isolated", "exact", "no-sync", "locked", "frozen", "no-project")

    @classmethod
    def works_with_context(cls, context: ContextProtocol) -> bool:
        if not context.config.is_uv_project:
            return False
        return bool(cls._uv_cmd_from_path())

    async def execute(
        self, cmd: Sequence[str], input: bytes | None = None, use_exec: bool = False
    ) -> PoeProcess:
        """
        Execute the given cmd as a subprocess via `uv run`.
        """

        uv_run_options = []

        if self._io.verbosity > 0:
            uv_run_options.append("-v")
        elif self._io.verbosity < 0:
            uv_run_options.append("-q")

        if self.working_dir:
            # Explicitly set the working directory and project directory for uv
            uv_run_options.append(f"--directory={self.working_dir}")
            uv_run_options.append(f"--project={self.context.config.project_dir}")

        uv_run_options.extend(
            f"--{key}={item}"
            for key in self.__uv_cli_options
            if (value := self.options.get(key))
            for item in ((value,) if isinstance(value, str) else value)
        )
        uv_run_options.extend(
            f"--{key}" for key in self.__uv_cli_flags if self.options.get(key)
        )

        # Run this task with `uv run`
        result = await self._execute_cmd(
            (self._uv_cmd(), "run", *uv_run_options, *cmd),
            input=input,
            use_exec=use_exec,
        )
        # The inner cmd may be a .bat/.cmd but _exec_via_subproc only sees uv.exe
        # as cmd[0], so check the original command here
        if self._is_windows and cmd[0].lower().endswith((".bat", ".cmd")):
            result.no_console_ctrl = True
        return result

    @classmethod
    def _uv_cmd(cls):
        if from_path := cls._uv_cmd_from_path():
            return from_path

        return "uv"

    @classmethod
    def _uv_cmd_from_path(cls):
        import shutil

        return shutil.which("uv")
