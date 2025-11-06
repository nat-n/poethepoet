from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TypedDict, Union

EmptyDict: Mapping = MappingProxyType({})


class EnvDefault(TypedDict):
    default: str


class EnvfileOption(TypedDict, total=False):
    expect: Union[str, Sequence[str]]
    optional: Union[str, Sequence[str]]
