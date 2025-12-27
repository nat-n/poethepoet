from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TypedDict

from ..options.annotations import option_annotation

EmptyDict: Mapping = MappingProxyType({})


@option_annotation
class EnvDefault(TypedDict):
    default: str


@option_annotation
class EnvfileOption(TypedDict, total=False):
    expected: str | Sequence[str]
    optional: str | Sequence[str]


EnvfileOption.__optional_keys__ = frozenset({"expected", "optional"})
