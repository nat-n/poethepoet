from __future__ import annotations

import os
import sys
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pastel import Pastel

POE_DEBUG = os.environ.get("POE_DEBUG", "0") == "1"


def guess_ansi_support(file) -> bool:
    if os.environ.get("NO_COLOR", "0")[0] != "0":
        # https://no-color.org/
        return False

    if (
        os.environ.get("GITHUB_ACTIONS", "false") == "true"
        and "PYTEST_CURRENT_TEST" not in os.environ
    ):
        return True

    return (
        (sys.platform != "win32" or "ANSICON" in os.environ)
        and hasattr(file, "isatty")
        and file.isatty()
    )


class PoeIO:
    """
    Manages input and output streams, verbosity levels, and message styling.
    """

    output: IO
    error_output: IO
    input: IO
    ansi_enabled: bool
    _baseline_verbosity: int
    _verbosity_offset: int | None

    _color: Pastel
    _default_io: PoeIO | None = None

    def __init__(
        self,
        *,
        parent: PoeIO | None = None,
        output: IO | None = None,
        error: IO | None = None,
        input: IO | None = None,
        baseline_verbosity: int | None = None,
        verbosity_offset: int | None = None,
        ansi: bool | None = None,
        make_default: bool = True,
    ):
        self.output = output or (parent.output if parent else sys.stdout)
        self.error_output = error or (parent.error_output if parent else sys.stderr)
        self.input = input or (parent.input if parent else sys.stdin)
        self.ansi_enabled = (
            ansi
            if ansi is not None
            else (parent.ansi_enabled if parent else guess_ansi_support(output))
        )

        if POE_DEBUG:
            self._baseline_verbosity = 3
            self._verbosity_offset = 0
        else:
            self._baseline_verbosity = (
                baseline_verbosity
                if baseline_verbosity is not None
                else parent._baseline_verbosity if parent else 0
            )
            self._verbosity_offset = (
                verbosity_offset
                if verbosity_offset is not None
                else parent._verbosity_offset if parent else None
            )

        if parent:
            self._color = parent._color
        else:
            self._init_colors()

        # First instance of PoeIO becomes the default IO
        if make_default:
            self.__class__._default_io = self

    def _init_colors(self):
        from pastel import Pastel

        self._color = Pastel(self.ansi_enabled)
        self._color.add_style("u", "default", options="underline")
        self._color.add_style("hl", "light_gray")
        self._color.add_style("em", "cyan")
        self._color.add_style("em2", "cyan", options="italic")
        self._color.add_style("em3", "blue")
        self._color.add_style("h2", "default", options="bold")
        self._color.add_style("h2-dim", "default", options="dark")
        self._color.add_style("action", "light_blue")
        self._color.add_style("error", "light_red", options="bold")
        self._color.add_style("warning", "light_red", options="bold")

    @classmethod
    def get_default_io(cls) -> PoeIO:
        if cls._default_io is None:
            cls._default_io = cls()
        return cls._default_io

    @property
    def verbosity(self) -> int:
        """
        Returns the current verbosity level, which is the base verbosity plus any
        verbosity offset from the command line arguments.
        """
        return self._baseline_verbosity + (self._verbosity_offset or 0)

    @property
    def verbosity_offset_was_set(self) -> bool:
        """
        Returns whether the verbosity offset was set explicitly, such as by the -v or -q
        CLI flags.
        """
        return self._verbosity_offset is not None

    def configure(
        self,
        *,
        ansi_enabled: bool | None = None,
        baseline: int | None = None,
        offset: int | None = None,
        dont_override: bool = False,
    ):
        may_override = not dont_override
        if ansi_enabled is not None and (self.ansi_enabled is None or may_override):
            self.ansi_enabled = ansi_enabled
            self._init_colors()
        if baseline is not None and (self._baseline_verbosity is None or may_override):
            self._baseline_verbosity = baseline
        if offset is not None and (self._verbosity_offset is None or may_override):
            self._verbosity_offset = offset

    def print(
        self,
        message: str,
        *values: Any,
        message_verbosity: int = 0,
        end: str = "\n",
    ):
        if self._check_verbosity(message_verbosity):
            if values:
                message = message % values
            self.write_out(message, end=end)

    def print_warning(
        self,
        message: str,
        *values: Any,
        message_verbosity: int = -1,
        prefix: str = "<warning>Warning:</warning> ",
        end: str = "\n",
    ):
        if self._check_verbosity(message_verbosity):
            if values:
                message = message % values
            self.write_err(prefix + message)

    def print_error(
        self,
        message: str,
        *values: Any,
        message_verbosity: int = -2,
        end: str = "\n",
    ):
        if self._check_verbosity(message_verbosity):
            if values:
                message = message % values
            self.write_err(message, end=end)

    def print_poe_action(
        self,
        arrow: str,
        action: str,
        message_verbosity: int = 0,
    ):
        if self._check_verbosity(message_verbosity):
            self.write_err(f"<hl>Poe {arrow}</hl> <action>{action}</action>")

    def print_debug(
        self,
        message: str,
        *values: Any,
        message_verbosity: int = 3,
        end: str = "\n",
    ):
        if self._check_verbosity(message_verbosity):
            if values:
                message = message % values
            self.write_err(message, end=end)

    def is_debug_enabled(self) -> bool:
        """
        Check if the debug verbosity level is enabled.
        """
        return self._check_verbosity(3)

    def _check_verbosity(self, message_verbosity: int) -> bool:
        """
        Check if the message should be printed based on the current verbosity level.
        """
        return message_verbosity <= (
            self._baseline_verbosity + (self._verbosity_offset or 0)
        )

    def write_out(self, message: str, *, end: str = "\n"):
        print(self._color.colorize(message), end=end, file=self.output, flush=True)

    def write_err(self, message: str, *, end: str = "\n"):
        print(
            self._color.colorize(message), end=end, file=self.error_output, flush=True
        )
