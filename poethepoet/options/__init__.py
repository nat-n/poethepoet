from __future__ import annotations

from keyword import iskeyword
from typing import TYPE_CHECKING, Any, get_type_hints

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from ..exceptions import ConfigValidationError
from .annotations import TypeAnnotation

NoValue = object()


class PoeOptions:
    """
    A special kind of config object that parses options ...
    """

    __annotations: dict[str, TypeAnnotation]

    def __init__(self, **options: Any):
        for key in self.get_fields():
            unsanitized_key = key.rstrip("_")
            if unsanitized_key in options:
                setattr(self, key, options[unsanitized_key])

    def __getattribute__(self, name: str):
        if name.endswith("_") and iskeyword(name[:-1]):
            # keyword attributes are accessed with a "_" suffix
            name = name[:-1]

        return object.__getattribute__(self, name)

    def __getattr__(self, name: str):
        if name not in self.get_fields():
            raise AttributeError(
                f"{self.__class__.__name__} has no such attribute {name!r}"
            )

        if name in self.__dict__:
            return self.__dict__[name]
        if hasattr(self.__class__, name):
            return getattr(self.__class__, name)
        if self.__is_optional(name):
            return None

        raise AttributeError(
            f"{self.__class__.__name__} has no value for option {name!r}"
        )

    def __str__(self):
        return (
            f"{self.__class__.__name__}("
            + ", ".join(
                f"{field}={getattr(self, field)!r}" for field in self.get_fields()
            )
            + ")"
        )

    @classmethod
    def parse(
        cls,
        source: Mapping[str, Any] | list,
        strict: bool = True,
        extra_keys: Sequence[str] = tuple(),
    ):
        config_keys = {
            key[:-1] if key.endswith("_") and iskeyword(key[:-1]) else key: type_
            for key, type_ in cls.get_fields().items()
        }
        if strict:
            for index, item in enumerate(cls.normalize(source, strict)):
                options = {}
                for key, value_type in config_keys.items():
                    if key in item:
                        options[key] = cls._parse_value(
                            index, key, item[key], value_type, strict
                        )
                    elif not hasattr(cls, cls._resolve_key(key)):
                        raise ConfigValidationError(
                            f"Missing required option {key!r}", index=index
                        )

                for key in item:
                    if key not in config_keys and key not in extra_keys:
                        raise ConfigValidationError(
                            f"Unrecognised option {key!r}", index=index
                        )

                result = cls(**options)
                result.validate()
                yield result

        else:
            for index, item in enumerate(cls.normalize(source, strict)):
                yield cls(
                    **{
                        key: cls._parse_value(index, key, item[key], value_type, strict)
                        for key, value_type in config_keys.items()
                        if key in item
                    }
                )

    @classmethod
    def _parse_value(
        cls, index: int, key: str, value: Any, value_type: Any, strict: bool
    ):
        if isinstance(value_type, type) and issubclass(value_type, PoeOptions):
            return value_type.parse(value, strict=strict)

        if strict:
            for error_msg in value_type.validate((key,), value):
                raise ConfigValidationError(error_msg, index=index)

        return value

    @classmethod
    def normalize(
        cls,
        config: Any,
        strict: bool = True,
    ):
        if isinstance(config, (list, tuple)):
            yield from config
        else:
            yield config

    def validate(self):
        pass

    def get(self, key: str, default: Any = NoValue) -> Any:
        """
        This is the most tolerant way to fetch a config value using the following
        strategies in priority order:

          1. Get the config value
          2. Return the default value provided as an argument
          3. Return the default value declared for this field
          4. Return the zero value for the type of this field
        """

        key = self._resolve_key(key)

        if key in self.__dict__:
            return self.__dict__[key]

        if default is NoValue:
            default = getattr(self.__class__, key, default)
        if default is NoValue:
            # Fallback to getting getting the zero value for the type of this attribute
            # e.g. 0, False, empty list, empty dict, etc
            annotation = self.get_fields().get(self._resolve_key(key))
            assert annotation
            return annotation.zero_value()

        return default

    def __is_optional(self, key: str):
        annotation = self.get_fields().get(self._resolve_key(key))
        assert annotation
        return annotation.is_optional

    def update(self, options_dict: dict[str, Any]):
        new_options_dict = {}
        for key in self.get_fields().keys():
            if key in options_dict:
                new_options_dict[key] = options_dict[key]
            elif hasattr(self, key):
                new_options_dict[key] = getattr(self, key)

    @classmethod
    def _resolve_key(cls, key: str) -> str:
        """
        Map from a config key to the config object attribute, which must not but a
        python keyword.
        """
        if iskeyword(key):
            return f"{key}_"
        return key

    @classmethod
    def get_fields(cls) -> dict[str, TypeAnnotation]:
        """
        Recent python versions removed inheritance for __annotations__
        so we have to implement it explicitly
        """
        if not hasattr(cls, "__annotations"):
            annotations = {}
            for base_cls in cls.__bases__:
                annotations.update(get_type_hints(base_cls))
            annotations.update(
                get_type_hints(cls, globalns=TypeAnnotation.get_type_hint_globals())
            )

            cls.__annotations = {
                key: TypeAnnotation.parse(type_)
                for key, type_ in annotations.items()
                if not key.startswith("_")
            }
        return cls.__annotations
