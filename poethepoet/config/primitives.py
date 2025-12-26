from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TypedDict

EmptyDict: Mapping = MappingProxyType({})


class EnvDefault(TypedDict):
    default: str


class EnvfileOption(TypedDict, total=False):
    expected: str | Sequence[str]
    optional: str | Sequence[str]


EnvfileOption.__optional_keys__ = frozenset({"expected", "optional"})
