import re

_TAG_PATTERN = re.compile(r"</?[^>]+>")


class Pastel:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def add_style(self, name: str, color: str, options: str | None = None) -> None:
        # Minimal stub used during tests. Styling is not required for assertions.
        return

    def colorize(self, message: str) -> str:
        # Strip markup tags so the caller receives plain text.
        return _TAG_PATTERN.sub("", message)
