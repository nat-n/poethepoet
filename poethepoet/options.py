import collections
from keyword import iskeyword
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

from .exceptions import ConfigValidationError

NoValue = object()


class PoeOptions:
    """
    A special kind of config object that parses options ...
    """

    __annotations: Dict[str, Type]

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

    @classmethod
    def parse(
        cls,
        source: Union[Mapping[str, Any], list],
        strict: bool = True,
        extra_keys: Sequence[str] = tuple(),
    ):
        config_keys = {
            key[:-1] if key.endswith("_") and iskeyword(key[:-1]) else key: vtype
            for key, vtype in cls.get_fields().items()
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
            expected_type: Union[Type, Tuple[Type, ...]] = cls._type_of(value_type)
            if not isinstance(value, expected_type):
                # Try format expected_type nicely in the error message
                if not isinstance(expected_type, tuple):
                    expected_type = (expected_type,)
                formatted_type = " | ".join(
                    type_.__name__ for type_ in expected_type if type_ is not type(None)
                )
                raise ConfigValidationError(
                    f"Option {key!r} should have a value of type: {formatted_type}",
                    index=index,
                )

            annotation = cls.get_annotation(key)
            if get_origin(annotation) is Literal:
                allowed_values = get_args(annotation)
                if value not in allowed_values:
                    raise ConfigValidationError(
                        f"Option {key!r} must be one of {allowed_values!r}",
                        index=index,
                    )

            # TODO: validate list/dict contents

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
            return self.__get_zero_value(key)

        return default

    def __get_zero_value(self, key: str):
        type_of_attr = self.type_of(key)
        if isinstance(type_of_attr, tuple):
            if type(None) in type_of_attr:
                # Optional types default to None
                return None
            type_of_attr = type_of_attr[0]
        assert type_of_attr
        return type_of_attr()

    def __is_optional(self, key: str):
        # TODO: precache optional options keys?
        type_of_attr = self.type_of(key)
        if isinstance(type_of_attr, tuple):
            return type(None) in type_of_attr
        return False

    def update(self, options_dict: Dict[str, Any]):
        new_options_dict = {}
        for key in self.get_fields().keys():
            if key in options_dict:
                new_options_dict[key] = options_dict[key]
            elif hasattr(self, key):
                new_options_dict[key] = getattr(self, key)

    @classmethod
    def type_of(cls, key: str) -> Optional[Union[Type, Tuple[Type, ...]]]:
        return cls._type_of(cls.get_annotation(key))

    @classmethod
    def get_annotation(cls, key: str) -> Optional[Type]:
        return cls.get_fields().get(cls._resolve_key(key))

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
    def _type_of(cls, annotation: Any) -> Union[Type, Tuple[Type, ...]]:
        if get_origin(annotation) is Union:
            result: List[Type] = []
            for component in get_args(annotation):
                component_type = cls._type_of(component)
                if isinstance(component_type, tuple):
                    result.extend(component_type)
                else:
                    result.append(component_type)
            return tuple(result)

        if get_origin(annotation) in (
            dict,
            Mapping,
            MutableMapping,
            collections.abc.Mapping,
            collections.abc.MutableMapping,
        ):
            return dict

        if get_origin(annotation) in (
            list,
            Sequence,
            collections.abc.Sequence,
        ):
            return list

        if get_origin(annotation) is Literal:
            return tuple({type(arg) for arg in get_args(annotation)})

        return annotation

    @classmethod
    def get_fields(cls) -> Dict[str, Any]:
        """
        Recent python versions removed inheritance for __annotations__
        so we have to implement it explicitly
        """
        if not hasattr(cls, "__annotations"):
            annotations = {}
            for base_cls in cls.__bases__:
                annotations.update(base_cls.__annotations__)
            annotations.update(cls.__annotations__)
            cls.__annotations = {
                key: type_
                for key, type_ in annotations.items()
                if not key.startswith("_")
            }
        return cls.__annotations
