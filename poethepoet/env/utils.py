from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class SpyDict(dict):
    """
    A dict subclass whose __getitem__ behaviour can be overridden via a spy callback.
    Keys missing from the content may be looked up with an optional fallback, which
    should return None for keys it doesn't have.
    """

    def __init__(
        self,
        content=(),
        *,
        getitem_spy: Callable | None = None,
        fallback: Callable[[str], str | None] | None = None,
    ):
        super().__init__(content)
        self._getitem_spy = getitem_spy
        self._fallback = fallback

    def __missing__(self, key: str):
        if self._fallback and (value := self._fallback(key)) is not None:
            return value
        raise KeyError(key)

    def __getitem__(self, key: str):
        value = super().__getitem__(key)
        if self._getitem_spy:
            return self._getitem_spy(self, key, value)
        return value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
