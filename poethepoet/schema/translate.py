"""
TypeAnnotation → JSON Schema translation.

Each TypeAnnotation subclass is translated by a dedicated function.
Translators access internal attributes of TypeAnnotation subclasses
(`_annotation`, `_values`, etc.) — this is intentional coupling: the
translator is a privileged consumer of the TypeAnnotation hierarchy,
on the same footing as `validate()` and `zero_value()`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from poethepoet.options.annotations import (
    AnyType,
    DictType,
    ListType,
    LiteralType,
    NoneType,
    PrimitiveType,
    TypeAnnotation,
    TypedDictType,
    UnionType,
)

if TYPE_CHECKING:
    from poethepoet.schema.context import SchemaContext

# Mapping from Python primitive types to JSON Schema `type:` strings.
_PRIMITIVE_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def translate_type(annotation: TypeAnnotation, ctx: SchemaContext) -> dict:
    """
    Translate a TypeAnnotation into a JSON Schema fragment (a dict).

    The translator does NOT mutate `ctx.definitions` itself; that's the
    schema-fragment hook's responsibility. The `ctx` parameter is passed
    through so future translators (e.g. recursive references) can lift
    definitions when needed.
    """
    if isinstance(annotation, PrimitiveType):
        return _translate_primitive(annotation)
    if isinstance(annotation, LiteralType):
        return _translate_literal(annotation)
    if isinstance(annotation, AnyType):
        return {}
    if isinstance(annotation, NoneType):
        return {"type": "null"}
    if isinstance(annotation, ListType):
        return _translate_list(annotation, ctx)
    if isinstance(annotation, DictType):
        return _translate_dict(annotation, ctx)
    if isinstance(annotation, TypedDictType):
        return _translate_typeddict(annotation, ctx)
    if isinstance(annotation, UnionType):
        return _translate_union(annotation, ctx)
    raise NotImplementedError(
        f"No translator yet for {type(annotation).__name__} (annotation: "
        f"{annotation!r})"
    )


def _translate_primitive(annotation: PrimitiveType) -> dict[str, Any]:
    """Translate str/int/float/bool with Metadata-driven constraints."""
    py_type = annotation._annotation
    schema: dict[str, Any] = {"type": _PRIMITIVE_TYPE_MAP[py_type]}

    # Layer in constraint metadata. Each is `None` if unset (explicitly-zero
    # values like minimum=0 are preserved, not silently dropped).
    if py_type is str:
        if (pattern := annotation.metadata_get("pattern")) is not None:
            schema["pattern"] = pattern
        if (min_length := annotation.metadata_get("min_length")) is not None:
            schema["minLength"] = min_length
        if (max_length := annotation.metadata_get("max_length")) is not None:
            schema["maxLength"] = max_length

    if py_type in (int, float):
        if (minimum := annotation.metadata_get("minimum")) is not None:
            schema["minimum"] = minimum
        if (maximum := annotation.metadata_get("maximum")) is not None:
            schema["maximum"] = maximum

    if (examples := annotation.metadata_get("examples")) is not None:
        schema["examples"] = examples

    return schema


def _translate_literal(annotation: LiteralType) -> dict[str, Any]:
    """
    Translate a Literal type. Emit `{type: <shared>, enum: [...]}` when
    all literal values share the same JSON type; emit just `{enum: [...]}`
    when they span types.
    """
    values = list(annotation._values)
    types = {_python_value_to_json_type(value) for value in values}
    if len(types) == 1 and (only := next(iter(types))) is not None:
        return {"type": only, "enum": values}
    return {"enum": values}


def _python_value_to_json_type(value: Any) -> str | None:
    """Map a literal value to the corresponding JSON Schema `type:` string."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    return None


def _translate_list(annotation: ListType, ctx: SchemaContext) -> dict[str, Any]:
    """
    Translate a ListType / Sequence[X] / tuple[X, ...] annotation.
    """
    schema: dict[str, Any] = {"type": "array"}

    if not isinstance(annotation._value_type, AnyType):
        schema["items"] = translate_type(annotation._value_type, ctx)

    if (min_length := annotation.metadata_get("min_length")) is not None:
        schema["minItems"] = min_length
    if (max_length := annotation.metadata_get("max_length")) is not None:
        schema["maxItems"] = max_length
    if (examples := annotation.metadata_get("examples")) is not None:
        schema["examples"] = examples

    return schema


def _translate_dict(annotation: DictType, ctx: SchemaContext) -> dict[str, Any]:
    """
    Translate a DictType / Mapping[str, V] annotation.

    Note: PoeOptions assumes all dict keys are strings; this matches
    JSON's key-as-string constraint.
    """
    schema: dict[str, Any] = {"type": "object"}

    if not isinstance(annotation._value_type, AnyType):
        schema["additionalProperties"] = translate_type(annotation._value_type, ctx)

    return schema


def _translate_typeddict(
    annotation: TypedDictType, ctx: SchemaContext
) -> dict[str, Any]:
    """
    Translate a TypedDictType. The class is `annotation._annotation`;
    fields and optional-key information are in `annotation._schema` /
    `annotation._optional_keys`.

    Descriptions are routed through ctx.description_for, which dispatches
    to extract_field_descriptions directly for TypedDicts (no MRO walk).
    """
    cls = annotation._annotation
    properties: dict[str, dict] = {}
    required: list[str] = []

    for field_name, field_annotation in annotation._schema.items():
        field_schema = translate_type(field_annotation, ctx)
        if description := ctx.description_for(cls, field_name):
            field_schema["description"] = description
        properties[field_name] = field_schema
        if field_name not in annotation._optional_keys:
            required.append(field_name)

    return {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
        "additionalProperties": False,
    }


def _translate_union(annotation: UnionType, ctx: SchemaContext) -> dict[str, Any]:
    """
    Translate a UnionType.

    Drops `NoneType` branches — Optional handling lives at the parent
    object level (a field's optionality is expressed by omitting it from
    the parent's `required` list, not by including null in its schema).

    If only one non-None branch remains, return that branch directly
    (no `anyOf` wrapper). If all branches are None, return a null schema.
    """
    non_none_branches = [
        branch for branch in annotation._value_types if not isinstance(branch, NoneType)
    ]

    if not non_none_branches:
        return {"type": "null"}

    if len(non_none_branches) == 1:
        return translate_type(non_none_branches[0], ctx)

    return {"anyOf": [translate_type(branch, ctx) for branch in non_none_branches]}
