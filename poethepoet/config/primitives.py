from types import MappingProxyType
from typing import Mapping, TypedDict

EmptyDict: Mapping = MappingProxyType({})


class EnvDefault(TypedDict):
    default: str
