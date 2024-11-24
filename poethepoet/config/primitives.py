from collections.abc import Mapping
from types import MappingProxyType
from typing import TypedDict

EmptyDict: Mapping = MappingProxyType({})


class EnvDefault(TypedDict):
    default: str
