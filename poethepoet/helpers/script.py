from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import ExpressionParseError

if TYPE_CHECKING:
    from collections.abc import Container

    from ..helpers.python import FunctionCall


def parse_script_reference(
    script_ref: str,
    parsed_args: dict[str, Any] | None = None,
    allowed_vars: Container[str] = tuple(),
) -> tuple[str, FunctionCall]:
    """
    Parses a script reference string and returns the module name and function call.

    Args:
        script_ref (str): A string representing the script reference, expected to
            include a module and function call (e.g., "module:function(arg1, arg2)").
        parsed_args (dict[str, Any] | None): A dictionary of arguments that have been
            parsed and are available for substitution.
        allowed_vars (Container[str]): An optional collection of variable names that may
            be referenced within the function call.

    Returns:
        tuple[str, FunctionCall]: A tuple containing:
            - The module name as a string.
            - A `FunctionCall` object representing the parsed function invocation.

    Raises:
        ExpressionParseError: If the script reference is contains invalid syntax or
        references variables that are not in scope.
    """

    from ..helpers.python import FunctionCall

    try:
        target_module, target_ref = script_ref.strip().split(":", 1)
    except ValueError:
        raise ExpressionParseError(f"Invalid script reference: {script_ref.strip()!r}")

    if target_ref.isidentifier():
        if parsed_args:
            function_call = FunctionCall(f"{target_ref}(**({parsed_args}))", target_ref)
        else:
            function_call = FunctionCall(f"{target_ref}()", target_ref)
    else:
        function_call = FunctionCall.parse(
            source=target_ref,
            arguments=set(parsed_args or tuple()),
            allowed_vars=allowed_vars,
        )

    return target_module, function_call


def validate_script_or_module_reference(content: str) -> None:
    """
    Validates a script or module reference string.

    Args:
        content (str): The script or module reference string to validate.
        parsed_args (dict[str, Any]): A dictionary of parsed arguments that may be
            referenced in the function call.
        allowed_vars (Container[str]): A collection of variable names that may be
            referenced within the function call.

    Raises:
        ConfigValidationError: If the content is not a valid script or module reference.
    """
    from ..exceptions import ConfigValidationError

    try:
        target_module, target_ref = content.strip().split(":", 1)
    except ValueError:
        target_module = content.strip()
        target_ref = None

    if not all(part.isidentifier() for part in target_module.split(".")):
        reference_type = "module" if target_ref is None else "callable"
        raise ConfigValidationError(
            f"Invalid module name in {reference_type} reference {content!r}"
        )

    if target_ref is None or target_ref.isidentifier():
        return

    try:
        from ..helpers.python import FunctionCall

        FunctionCall.parse(source=target_ref, arguments=set())
    except (ValueError, ExpressionParseError):
        raise ConfigValidationError(
            f"Invalid callable reference {content!r}\n"
            "(expected something like `module:callable` or `module:callable()`)"
        )
