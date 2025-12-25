from __future__ import annotations

import types
import typing
from collections.abc import Iterator, Mapping, MutableMapping, Sequence
from typing import (
    Annotated,
    Any,
    Literal,
    Optional,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)


class Metadata:
    __slots__ = ("config_name",)

    def __init__(self, *, config_name: str | None = None):
        self.config_name = config_name


class TypeAnnotation:
    """
    This class and its descendants provide a convenient model for parsing and
    enforcing pythonic type annotations for PoeOptions.
    """

    __slots__ = ("_annotation", "_metadata")

    @classmethod
    def get_type_hint_globals(cls):
        return {
            "Annotated": Annotated,
            "Any": Any,
            "Optional": Optional,
            "Mapping": Mapping,
            "MutableMapping": MutableMapping,
            "typing.Mapping": typing.Mapping,
            "typing.MutableMapping": typing.MutableMapping,
            "Sequence": Sequence,
            "typing.Sequence": typing.Sequence,
            "Literal": Literal,
            "Union": Union,
            "TypeAnnotation": cls,
            "Metadata": Metadata,
        }

    @staticmethod
    def parse(annotation: Any):
        origin = get_origin(annotation)

        # Support Annotated[T, Metadata(...)] so metadata can be
        # propagated into created TypeAnnotation instances.
        metadata = None
        if origin is Annotated:
            args = get_args(annotation)
            # args[0] is the underlying annotation, args[1:] are metadata
            annotation = args[0]
            origin = get_origin(annotation)
            # pick first metadata object (commonly Metadata)
            if len(args) > 1:
                metadata = args[1]

        if annotation in (str, int, float, bool):
            return PrimitiveType(annotation, metadata)

        elif annotation is dict or origin in (
            dict,
            Mapping,
            MutableMapping,
            typing.Mapping,
            typing.MutableMapping,
        ):
            return DictType(annotation, metadata)

        elif annotation is list or origin in (
            list,
            tuple,
            Sequence,
            typing.Sequence,
        ):
            return ListType(annotation, metadata)

        elif origin is Literal:
            return LiteralType(annotation, metadata)

        elif origin in (types.UnionType, Union):
            return UnionType(annotation, metadata)

        elif annotation is Any:
            return AnyType(annotation, metadata)

        elif annotation in (None, type(None)):
            return NoneType(annotation, metadata)

        elif typing.is_typeddict(annotation):
            return TypedDictType(annotation, metadata)

        raise ValueError(f"Cannot parse TypeAnnotation for annotation: {annotation}")

    def __init__(self, annotation: Any, metadata: Any = None):
        self._annotation = annotation
        self._metadata = metadata

    def metadata_get(self, key: str, default: Any = None) -> Any:
        if self._metadata and (value := getattr(self._metadata, key, None)):
            return value
        return default

    @property
    def is_optional(self) -> bool:
        return False

    @property
    def simple_type(self) -> Any:
        return self._annotation

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        raise NotImplementedError

    def zero_value(self) -> Any:
        return None

    @staticmethod
    def _format_path(path: tuple[str | int, ...]):
        return "".join(
            (f"[{part}]" if isinstance(part, int) else f".{part}") for part in path
        ).strip(".")


class DictType(TypeAnnotation):
    __slots__ = ("_value_type",)

    def __init__(self, annotation: Any, metadata: Any = None):
        super().__init__(annotation, metadata)
        if args := get_args(annotation):
            assert args[0] is str
            self._value_type = TypeAnnotation.parse(get_args(annotation)[1])
        else:
            self._value_type = AnyType()

    def __str__(self):
        if isinstance(self._value_type, AnyType):
            return "dict"
        return f"dict[str, {self._value_type}]"

    @property
    def simple_type(self) -> Any:
        return dict

    def zero_value(self) -> dict:
        return {}

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if not isinstance(value, dict):
            yield f"Option {self._format_path(path)!r} must be a dict"

        if isinstance(self._value_type, AnyType):
            return

        # We assume dict keys can only be strings so no need to check them
        for key, dict_value in value.items():
            yield from self._value_type.validate((*path, key), dict_value)


class TypedDictType(TypeAnnotation):
    __slots__ = ("_optional_keys", "_schema")

    def __init__(self, annotation: Any, metadata: Any = None):
        super().__init__(annotation, metadata)
        self._schema = {
            key: TypeAnnotation.parse(type_)
            for key, type_ in get_type_hints(annotation, include_extras=True).items()
        }
        self._optional_keys: frozenset[str] = getattr(
            annotation, "__optional_keys__", frozenset()
        )

    def __str__(self):
        return (
            "dict("
            + ", ".join(f"{key}: {value}" for key, value in self._schema.items())
            + ")"
        )

    @property
    def simple_type(self) -> Any:
        return dict

    def zero_value(self) -> dict:
        return {
            key: value_type.zero_value()
            for key, value_type in self._schema.items()
            if key not in self._optional_keys
        }

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if not isinstance(value, dict):
            yield f"Option {self._format_path(path)!r} must be a dict"

        for key, value_type in self._schema.items():
            if key not in value:
                if key not in self._optional_keys:
                    yield (
                        f"Option {self._format_path(path)!r} "
                        f"missing required key: {key}"
                    )
                continue
            yield from value_type.validate((*path, key), value[key])

        for key in set(value) - set(self._schema):
            yield f"Option {self._format_path(path)!r} contains unexpected key: {key}"


class ListType(TypeAnnotation):
    __slots__ = ("_type", "_value_type")

    def __init__(self, annotation: Any, metadata: Any = None):
        super().__init__(annotation, metadata)
        self._type = get_origin(annotation) or (tuple if annotation is tuple else list)
        if args := get_args(annotation):
            self._value_type = TypeAnnotation.parse(args[0])
            if self._type is tuple:
                assert (
                    args[1] is ...
                ), "ListType only accepts tuples with any length type"
        else:
            self._value_type = AnyType()

    def __str__(self):
        # Even if the type is tuple, only use list for error reporting etc
        if isinstance(self._value_type, AnyType):
            return "list"
        return f"list[{self._value_type}]"

    @property
    def simple_type(self) -> Any:
        return dict

    def zero_value(self) -> list:
        return []

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if not isinstance(value, (list, tuple)):
            yield f"Option {self._format_path(path)!r} must be a list"

        if isinstance(self._value_type, AnyType):
            return

        for idx, item in enumerate(value):
            yield from self._value_type.validate((*path, idx), item)


class LiteralType(TypeAnnotation):
    __slots__ = ("_values",)

    def __init__(self, annotation: Any, metadata: Any = None):
        super().__init__(annotation, metadata)
        self._values = get_args(annotation)

    def __str__(self):
        return " | ".join(
            repr(type_) for type_ in self._values if type_ is not type(None)
        )

    @property
    def simple_type(self) -> Any:
        return type(self._values[0])

    def zero_value(self) -> Any:
        return self._values[0]

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if value not in self._values:
            yield f"Option {self._format_path(path)!r} must be one of {self._values!r}"


class UnionType(TypeAnnotation):
    __slots__ = ("_value_types",)

    def __init__(self, annotation: Any, metadata: Any = None):
        super().__init__(annotation, metadata)
        self._value_types = tuple(
            TypeAnnotation.parse(arg) for arg in get_args(annotation)
        )

    @property
    def is_optional(self) -> bool:
        return any(isinstance(value_type, NoneType) for value_type in self._value_types)

    def __str__(self):
        return " | ".join(
            {
                str(type_)
                for type_ in self._value_types
                if not isinstance(type_, NoneType)
            }
        )

    @property
    def simple_type(self) -> Any:
        return next(
            vt for vt in self._value_types if not isinstance(vt, NoneType)
        ).simple_type

    def zero_value(self) -> Any:
        if any(isinstance(value_type, NoneType) for value_type in self._value_types):
            # If the Type can be None then that's the zero value
            return None
        return self._value_types[0].zero_value()

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if len(self._value_types) == 2:
            # In case this is a simple optional type then just validate the wrapped type
            # This results in more specific validation errors
            if isinstance(self._value_types[1], NoneType):
                yield from self._value_types[0].validate(path, value)
                return
            elif isinstance(self._value_types[0], NoneType):
                yield from self._value_types[1].validate(path, value)
                return

        for value_type in self._value_types:
            errors = next(value_type.validate(path, value), None)
            if errors is None:
                break
        else:
            yield (
                f"Option {self._format_path(path)!r} must have a value of type: {self}"
            )


class AnyType(TypeAnnotation):
    def __init__(self, annotation: Any = Any, metadata: Any = None):
        super().__init__(annotation, metadata)

    def __str__(self):
        return "Any"

    @property
    def simple_type(self) -> Any:
        return None

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if False:
            yield ""
        return


class NoneType(TypeAnnotation):
    def __init__(self, annotation: Any = None, metadata: Any = None):
        super().__init__(annotation or type(None), metadata)

    @property
    def simple_type(self) -> Any:
        return None

    def __str__(self):
        return "None"

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if value is not None:
            # this should probably never happen
            yield f"Option {self._format_path(path)!r} must be None"


class PrimitiveType(TypeAnnotation):
    def __str__(self):
        return self._annotation.__name__

    def zero_value(self) -> Any:
        return self._annotation()

    def validate(self, path: tuple[str | int, ...], value: Any) -> Iterator[str]:
        if not isinstance(value, self._annotation):
            yield (
                f"Option {self._format_path(path)!r} must have a value of type: {self}"
            )
