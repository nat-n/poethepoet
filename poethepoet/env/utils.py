from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class SpyDict(dict):
    """
    A dict subclass whose __getitem__ behaviour can be overridden via a spy callback.
    """

    def __init__(self, content=(), *, getitem_spy: Callable | None = None):
        super().__init__(content)
        self._getitem_spy = getitem_spy

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if self._getitem_spy:
            return self._getitem_spy(self, key, value)
        return value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
