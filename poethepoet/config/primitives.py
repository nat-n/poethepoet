from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TypedDict

from ..options.annotations import option_annotation

EmptyDict: Mapping = MappingProxyType({})


@option_annotation
class EnvDefault(TypedDict):
    default: str
    """
    A default value for an environment variable that will be used only if the
    variable is not already set.
    """


@option_annotation
class EnvfileOption(TypedDict, total=False):
    expected: str | Sequence[str]
    """
    Provide one or more env files to be loaded before running this task. Emit a
    warning if any specified envfile is missing.
    """

    optional: str | Sequence[str]
    """
    Provide one or more env files to be loaded before running this task. Do not
    emit a warning even if a specified envfile is missing.
    """


EnvfileOption.__optional_keys__ = frozenset({"expected", "optional"})
