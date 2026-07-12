from __future__ import annotations

ANSI_RESET = "\x1b[0m"


class StyleCode:
    """
    A callable that wraps text in ANSI SGR codes, or returns it unchanged when
    the palette it belongs to has ansi disabled. The palette is the single
    authority for that setting, so a reference to a StyleCode always reflects
    the current ANSI configuration.
    """

    __slots__ = ("_palette", "_prefix")

    def __init__(self, palette: Style, *codes: int):
        self._palette = palette
        self._prefix = f"\x1b[{';'.join(map(str, codes))}m"

    def __call__(self, text: object) -> str:
        """
        Apply this style to the given text if the palette has ansi enabled.

        Any length based formatting logic such as padding should be applied to
        the text before styling it.
        """
        if not self._palette.ansi_enabled:
            return str(text)
        # Re-assert this style after any embedded reset so that wrapping an
        # already styled fragment composes instead of truncating the outer style
        return (
            self._prefix
            + str(text).replace(ANSI_RESET, ANSI_RESET + self._prefix)
            + ANSI_RESET
        )


class Style:
    """
    The palette of styles for poe's own output. Styles are named for the kind
    of information they mark, not for their appearance — when styling a new
    message, reuse an existing style if the meaning matches, or add a new one
    (even if it renders the same as another) if it doesn't.
    """

    ansi_enabled: bool
    """
    Whether styles in this palette apply ANSI codes. Mutating this attribute is
    also effective for any code holding a reference to one of the StyleCode
    members of this palette.
    """

    def __init__(self, ansi_enabled: bool = True):
        self.ansi_enabled = ansi_enabled

        # headings & structure
        self.title = StyleCode(self, 1)
        self.heading = StyleCode(self, 1)
        self.task_group = StyleCode(self, 32)
        self.empty_state = StyleCode(self, 2)

        # identifiers the user can act on
        self.task_name = StyleCode(self, 36)
        self.arg_name = StyleCode(self, 34)
        self.program = StyleCode(self, 4)

        # runtime narration
        self.poe_prefix = StyleCode(self, 37)
        self.action = StyleCode(self, 94)

        # status
        self.result = StyleCode(self, 36, 3)
        self.version = StyleCode(self, 36)
        self.error = StyleCode(self, 91, 1)
        self.warning = StyleCode(self, 91, 1)
