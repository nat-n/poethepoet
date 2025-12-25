from __future__ import annotations

from typing import TYPE_CHECKING, Any, get_type_hints

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

from ..exceptions import ConfigValidationError
from .annotations import TypeAnnotation

NoValue = object()


class PoeOptions:
    """
    Base class for poe config objects, for parsing, validating, and normalizing config.

    Think of it like a lightweight stand in for pydantic.

    Options are declared as class attributes with type annotations, and optional
    metadata.

    Supported metadata includes:
    - config_name: the name of the config key to parse from if different from the
        attribute name

    Subclasses may implement:
    - normalize() to coerce alternative config schema variants
    - validate() to implement custom validation logic after parsing

    Options may be accessed via attribute access, or via the get() method, which
    supports default values and tolerant lookup.
    """

    __fields: dict[str, TypeAnnotation]
    __field_attributes: dict[str, str]

    def __init__(self, **options: Any):
        for key in self.get_fields():
            if key in options:
                super().__setattr__(key, options[key])

    def __getattr__(self, name: str):
        if name not in self.get_fields():
            raise AttributeError(
                f"{self.__class__.__name__} has no such attribute {name!r}"
            )

        if name in self.__dict__:
            # Return the value from the instance dictionary
            return self.__dict__[name]
        if hasattr(self.__class__, name):
            # Fallback to class attribute (default value)
            return getattr(self.__class__, name)
        if self.__is_optional(name):
            # Optional field not set; return None
            return None

        raise AttributeError(
            f"{self.__class__.__name__} has no value for option {name!r}"
        )

    def __setattr__(self, name, value):
        """Prevent setting attributes on config objects after creation."""
        raise NotImplementedError

    def __delattr__(self, name):
        """Prevent deleting attributes on config objects after creation."""
        raise NotImplementedError

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
        source: Mapping[str, Any] | list[Mapping[str, Any]],
        strict: bool = True,
        extra_keys: Sequence[str] = (),
    ) -> Iterator[PoeOptions]:
        """
        Parse the given source mapping or list of mappings into PoeOptions objects.

        If strict is True, perform validation and raise ConfigValidationError if
        expected options are missing or invalid, or unexpected options are present.

        extra_keys may be provided to allow additional unrecognized keys in strict mode.

        If an option has has a config_name specified then this name will be parsed from
        the input instead of the actual attribute name.
        """
        config_map: dict[str, tuple[str, Any]] = {
            type_annotation.metadata_get("config_name", attr_name): (
                attr_name,
                type_annotation,
            )
            for attr_name, type_annotation in cls.get_fields().items()
        }
        if strict:
            for index, item in enumerate(cls.normalize(source, strict)):
                options = {}
                for config_name, (field_name, value_type) in config_map.items():
                    if config_name in item:
                        value = item[config_name]
                        for error_msg in value_type.validate((config_name,), value):
                            raise ConfigValidationError(error_msg, index=index)
                        options[field_name] = value

                    elif not hasattr(
                        cls, cls.get_field_attribute(field_name) or field_name
                    ):
                        raise ConfigValidationError(
                            f"Missing required option {config_name!r}", index=index
                        )

                for key in item:
                    if key not in config_map and key not in extra_keys:
                        raise ConfigValidationError(
                            f"Unrecognized option {key!r}", index=index
                        )

                result = cls(**options)
                result.validate()
                yield result

        else:
            for item in cls.normalize(source, strict):
                yield cls(
                    **{
                        field_name: item[config_name]
                        for config_name, (field_name, _) in config_map.items()
                        if config_name in item
                    }
                )

    @classmethod
    def normalize(cls, config: Any, strict: bool = True):
        """
        This may be overridden by subclasses to coerce alternative variants of the
        config schema to the 'normal' variant.
        """
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

          1. Get the config value if it was set explicitly
          2. Return the default value provided as an argument
          3. Return the default value declared for this field
          4. Return the zero value for the type of this field

        A key may reference a field by its attribute name or its config_name.
        """

        resolved_key = self.get_field_attribute(key) or ""

        if resolved_key in self.__dict__:
            return self.__dict__[resolved_key]

        if default is NoValue:
            # Lookup the default value declared on the class attribute
            default = getattr(self.__class__, resolved_key, default)
            if default is NoValue:
                # Fallback to getting getting the zero value for the relevant type
                # e.g. 0, False, empty list, empty dict, etc
                annotation = self.get_fields().get(resolved_key)
                assert annotation
                return annotation.zero_value()

        return default

    def __is_optional(self, field_name: str):
        if (resolved_key := self.get_field_attribute(field_name)) is None:
            raise KeyError(f"No such config option {field_name!r}")
        return self.get_fields()[resolved_key].is_optional

    @classmethod
    def get_field_type(cls, key: str) -> type | None:
        """
        Return the class of the given field. If the field is unknown return None.
        If the type is complex, return just the origin.
        If the field is a union, return the first non-None arg.
        """
        if (resolved_key := cls.get_field_attribute(key)) is None:
            return None
        return cls.get_fields()[resolved_key].simple_type

    @classmethod
    def get_fields(cls) -> dict[str, TypeAnnotation]:
        """
        Recent python versions removed inheritance for __annotations__
        so we have to implement it explicitly. We also use our own TypeAnnotation
        class to wrap type annotations with metadata and help with validation.
        """
        if not hasattr(cls, "__fields"):
            cls_type_hints = {}
            for base_cls in cls.__bases__:
                cls_type_hints.update(get_type_hints(base_cls, include_extras=True))
            cls_type_hints.update(
                get_type_hints(
                    cls,
                    globalns=TypeAnnotation.get_type_hint_globals(),
                    include_extras=True,
                )
            )

            cls.__fields = {
                key: TypeAnnotation.parse(type_)
                for key, type_ in cls_type_hints.items()
                if not key.startswith("_")
            }
            field_keys = {key: key for key in cls.__fields.keys()}
            for field_key, field_annotation in cls.__fields.items():
                if config_name := field_annotation.metadata_get("config_name"):
                    field_keys[config_name] = field_key

        return cls.__fields

    @classmethod
    def get_field_attribute(cls, field_name: str) -> str | None:
        """
        Lookup an attribute name from either the config_name or the attribute name.
        """
        if not hasattr(cls, "__field_attributes"):
            cls.__field_attributes = {}
            for attribute, field_annotation in cls.get_fields().items():
                if attribute in cls.__field_attributes:
                    raise RuntimeError(
                        f"Duplicate field name {attribute!r} in {cls.__name__}"
                    )
                if config_name := field_annotation.metadata_get("config_name"):
                    if config_name in cls.__field_attributes:
                        raise RuntimeError(
                            f"Duplicate field name {config_name!r} in {cls.__name__}"
                        )
                    cls.__field_attributes[config_name] = attribute
                cls.__field_attributes[attribute] = attribute

        return cls.__field_attributes.get(field_name)
