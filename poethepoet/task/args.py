from __future__ import annotations

import os
from contextlib import redirect_stderr
from typing import IO, TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from argparse import ArgumentParser
    from collections.abc import Iterator, Mapping, Sequence
    from typing import Annotated

    from ..env.task_env import TaskEnv
    from ..io import PoeIO
    from ..options.annotations import Metadata

from ..exceptions import ConfigValidationError, ExecutionError
from ..options import PoeOptions

ArgParams = dict[str, Any]
ArgsDef = list[str] | list[ArgParams] | dict[str, ArgParams]

arg_types: dict[str, type] = {
    "string": str,
    "float": float,
    "integer": int,
    "boolean": bool,
}


class ArgSpec(PoeOptions):
    default: str | int | float | bool | None = None
    """
    The default value for the argument when not provided.
    """

    help: str = ""
    """
    A short description of the argument to include in the documentation of the
    task.
    """

    name: str
    """
    The name of the argument.
    """

    options: Annotated[Sequence[str], Metadata(min_items=1)]
    """
    A list of options to be provided along with the argument.
    """

    positional: bool | str = False
    """
    Indicates if the argument is positional. If a string is provided, it is used
    as the dest name for the argument in argparse.
    """

    required: bool = False
    """
    Indicates if the argument is required.
    """

    type: Literal["string", "float", "integer", "boolean"] = "string"
    """
    The type of the argument.
    """

    true_string: str | None = None
    """
    Literal string to expose for a true boolean argument in parameter expansion
    and the environment. Defaults to "True" when omitted.
    """

    false_string: str | None = None
    """
    Literal string to expose for a false boolean argument in parameter expansion
    and the environment. The variable is unset when omitted.
    """

    multiple: bool | int = False
    """
    Indicates if multiple values are allowed for the argument. If an integer is
    given, exactly that many values are expected.
    """

    choices: Sequence[str] | Sequence[float] | Sequence[int] | None = None
    """
    Constrain the accepted values for an argument to a fixed set.
    """

    @classmethod
    def normalize(
        cls, source: Mapping[str, Any] | list[Mapping[str, Any]], strict: bool = True
    ):
        """
        Because arguments can be declared with different structures
        (i.e. dict or list), this function normalizes the input into a list of
        dictionaries with necessary keys.

        This is also where we do any validation that requires access to the raw
        config.
        """
        if isinstance(source, list):
            for item in source:
                if isinstance(item, str):
                    yield {"name": item, "options": (f"--{item.lstrip('_')}",)}
                elif isinstance(item, dict):
                    yield dict(
                        item,
                        options=cls._get_arg_options_list(item, strict=strict),
                    )
                elif strict:
                    raise ConfigValidationError(
                        f"Argument {item!r} has invalid type, a string or dict is "
                        "expected"
                    )

        elif isinstance(source, dict):
            for name, params in source.items():
                if not isinstance(params, dict):
                    raise ConfigValidationError(
                        f"Invalid configuration for arg {name!r}, expected dict"
                    )
                if strict and "name" in params:
                    raise ConfigValidationError(
                        f"Unexpected 'name' option for argument {name!r}"
                    )
                yield dict(
                    params,
                    name=name,
                    options=cls._get_arg_options_list(params, name, strict),
                )

    @classmethod
    def parse(
        cls,
        source: Mapping[str, Any] | list,
        strict: bool = True,
        extra_keys: Sequence[str] = (),
    ) -> Iterator[ArgSpec]:
        """
        Override parse function to perform validations that require considering all
        argument declarations at once.
        """
        try:
            result: tuple[ArgSpec] = tuple(super().parse(source, strict, extra_keys))  # type: ignore[assignment]
        except ConfigValidationError as error:
            PoeTaskArgs._enrich_config_error(error, cast("ArgsDef", source))
            raise

        if strict:
            arg_names = set()
            option_args: dict[str, str] = {}
            positional_dests: dict[str, str] = {}
            # Every identifier an arg occupies while its value is parsed and
            # exposed: the argparse dest, and the (dash normalized) name.
            identifiers: dict[str, str] = {}
            positional_multiple = None
            for arg in result:
                if arg.name in arg_names:
                    raise ConfigValidationError(
                        f"Duplicate argument name {arg.name!r}",
                        context=f"Invalid argument {arg.name!r} declared",
                    )
                arg_names.add(arg.name)

                if not arg.positional:
                    for option in ArgSpec._get_arg_options_list(arg, arg.name, strict):
                        if option in option_args:
                            raise ConfigValidationError(
                                f"Arguments {option_args[option]!r} and"
                                f" {arg.name!r} generate the same CLI"
                                f" option {option!r}",
                            )
                        option_args[option] = arg.name

                if arg.positional:
                    dest = arg.options[0]
                    if dest in positional_dests:
                        raise ConfigValidationError(
                            f"Arguments {positional_dests[dest]!r} and"
                            f" {arg.name!r} generate the same positional"
                            f" identifier {dest!r}",
                            context=f"Invalid argument {arg.name!r} declared",
                        )
                    positional_dests[dest] = arg.name

                    if positional_multiple:
                        raise ConfigValidationError(
                            f"Only the last positional arg of task may accept"
                            f" multiple values (not {positional_multiple!r}).",
                            context=f"Invalid argument {arg.name!r} declared",
                        )
                    if arg.multiple:
                        positional_multiple = arg.name

                dest = arg.options[0] if arg.positional else arg.name
                arg_identifiers = {
                    arg.name.replace("-", "_"),
                    dest.replace("-", "_"),
                }
                for identifier in sorted(arg_identifiers):
                    if identifier in identifiers:
                        raise ConfigValidationError(
                            f"Arguments {identifiers[identifier]!r} and"
                            f" {arg.name!r} map to the same argument"
                            f" identifier {identifier!r}",
                            context=f"Invalid argument {arg.name!r} declared",
                        )
                identifiers.update(
                    (identifier, arg.name) for identifier in arg_identifiers
                )
        yield from result

    @staticmethod
    def _get_arg_options_list(
        arg: Mapping[str, Any] | ArgSpec, name: str | None = None, strict: bool = True
    ):
        positional = arg.get("positional", False)
        name = name or arg.get("name")
        stripped = (name or "").lstrip("_")
        if positional:
            if strict and arg.get("options"):
                raise ConfigValidationError(
                    f"Positional argument {name!r} may not declare options"
                )
            # Fill in the options param in a way that makes sense for argparse.
            # Underscores are stripped from the dest so private positional args
            # don't render as ``_foo`` in help; the original name is restored
            # after parsing in PoeTaskArgs.parse so the var stays private.
            if isinstance(positional, str):
                return [positional]
            return [stripped or name]
        return tuple(arg.get("options", [f"--{stripped}"]))

    @classmethod
    def __schema_fragment__(cls, ctx: Any) -> dict:
        """
        Override: `options` is normalizer-supplied (derived from `name`
        if not provided), so it shouldn't be required in the schema.

        Also encode the runtime constraint that boolean defaults must be
        either a real bool or a recognised string literal — the same set
        accepted by ``_coerce_bool``. Template-shaped strings (containing
        ``${``) are passed through; their resolved value is re-checked at
        runtime. The pattern uses explicit case alternation rather than
        ``(?i)`` because JSON Schema mandates ECMA-262 regex, which does
        not support inline flags. Defaults of integer and float args are
        constrained in the same way.
        """
        fragment = super().__schema_fragment__(ctx)
        fragment["required"] = sorted(
            key for key in fragment.get("required", []) if key != "options"
        )
        fragment["allOf"] = [
            {
                "if": {
                    "properties": {"type": {"const": "boolean"}},
                    "required": ["type"],
                },
                "then": {
                    "properties": {
                        "default": {
                            "anyOf": [
                                {"type": "boolean"},
                                {
                                    "type": "string",
                                    "pattern": (
                                        r"^(\s*([Tt]([Rr][Uu][Ee])?"
                                        r"|[Ff]([Aa][Ll][Ss][Ee])?|0|1)?\s*"
                                        r"|.*\$\{.*)$"
                                    ),
                                },
                            ]
                        }
                    }
                },
                "else": {"properties": {"true_string": False, "false_string": False}},
            },
            # Numeric args reject boolean defaults, and an integer arg's literal
            # string default must look like an int (see ``_convert_default``).
            {
                "if": {
                    "properties": {"type": {"const": "integer"}},
                    "required": ["type"],
                },
                "then": {
                    "properties": {
                        "default": {
                            "anyOf": [
                                {"type": "integer"},
                                {
                                    "type": "string",
                                    "pattern": (
                                        r"^(\s*[+-]?[0-9]+(_[0-9]+)*\s*|.*\$\{.*)$"
                                    ),
                                },
                            ]
                        }
                    }
                },
            },
            {
                "if": {
                    "properties": {"type": {"const": "float"}},
                    "required": ["type"],
                },
                "then": {
                    "properties": {
                        "default": {"anyOf": [{"type": "number"}, {"type": "string"}]}
                    }
                },
            },
        ]
        return fragment

    def validate(self):
        try:
            return self._validate()
        except ConfigValidationError as error:
            error.context = f"Invalid argument {self.name!r} declared"
            raise

    def _validate(self):
        for option in ("true_string", "false_string"):
            if self.get(option) is not None and self.type != "boolean":
                raise ConfigValidationError(
                    f"Option {option!r} requires argument type 'boolean'"
                )

        if not self.name.replace("-", "_").isidentifier():
            raise ConfigValidationError(
                f"Argument name {self.name!r} is not a valid 'identifier',\n"
                f"see the following documentation for details "
                f"https://docs.python.org/3/reference/lexical_analysis.html#identifiers"
            )

        if self.positional:
            if self.type == "boolean":
                raise ConfigValidationError(
                    f"Positional argument {self.name!r} may not have type 'boolean'"
                )

            if isinstance(self.positional, str) and not self.positional.isidentifier():
                raise ConfigValidationError(
                    f"positional name {self.positional!r} for arg {self.name!r} is "
                    "not a valid 'identifier'\n"
                    "see the following documentation for details "
                    "https://docs.python.org/3/reference/lexical_analysis.html#identifiers"
                )
        else:
            for option in self.options:
                if not option.strip():
                    raise ConfigValidationError(
                        "Invalid empty value in CLI options list"
                    )
                if option[0] != "-":
                    suggestion = f"-{option}" if len(option) == 1 else f"--{option}"
                    raise ConfigValidationError(
                        f"Invalid CLI option provided {option!r}, did you mean "
                        f"{suggestion!r}?"
                    )

        if (
            not isinstance(self.multiple, bool)
            and isinstance(self.multiple, int)
            and self.multiple < 2
        ):
            raise ConfigValidationError(
                "The 'multiple' option accepts a boolean or integer >= 2"
            )

        if self.multiple is not False and self.type == "boolean":
            raise ConfigValidationError(
                "Argument with type 'boolean' may not declare option 'multiple'"
            )

        # Templated defaults are checked at runtime once the template has
        # been resolved (see PoeTaskArgs._get_argument_params and
        # PoeTaskArgs._resolve_default).
        if self.default is not None and not (
            isinstance(self.default, str) and "${" in self.default
        ):
            if self.type == "boolean":
                _coerce_bool(self.default)
            else:
                _convert_default(self.default, self.type)

        # Ensure choices are compatible with type
        if self.choices is not None:
            arg_type = arg_types.get(self.type, str)
            for choice in self.choices:
                if not isinstance(choice, arg_type) or isinstance(choice, bool):
                    raise ConfigValidationError(
                        f"Argument {self.name!r} has invalid choice value {choice!r} "
                        f"that does not match type the configured {self.type!r}. "
                        "(maybe update the type option on the argument?)"
                    )
            if (
                self.default is not None
                and (not isinstance(self.default, str) or "${" not in self.default)
                and self.default not in self.choices
            ):
                raise ConfigValidationError(
                    f"Argument {self.name!r} has default value {self.default!r} that "
                    f"is not included in the configured choices {self.choices!r}"
                )
            if self.type == "boolean":
                raise ConfigValidationError(
                    f"Argument {self.name!r} with type 'boolean' may not declare "
                    f"option 'choices'"
                )


class PoeTaskArgs:
    _args: tuple[ArgSpec, ...]

    def __init__(self, args_def: ArgsDef, task_name: str, io: PoeIO):
        self._task_name = task_name
        self._args = self._parse_args_def(args_def)
        self._io = io

    def _parse_args_def(self, args_def: ArgsDef) -> tuple[ArgSpec, ...]:
        try:
            return tuple(ArgSpec.parse(args_def))
        except ConfigValidationError as error:
            self._enrich_config_error(error, args_def, self._task_name)
            raise

    @classmethod
    def get_help_content(
        cls, args_def: ArgsDef | None, task_name: str, suppress_errors: bool = False
    ) -> list[tuple[tuple[str, ...], str, str]]:
        if args_def is None:
            return []

        def format_arg_details(arg) -> str:
            parts: list[str] = []
            if default := arg.get("default"):
                parts.append(f"default: {default}")
            if choices := arg.get("choices"):
                parts.append(f"choices: {', '.join(map(repr, choices))}")
            if parts:
                return f"[{'; '.join(parts)}]"
            return ""

        try:
            return [
                (
                    cast("tuple[str, ...]", arg["options"]),
                    str(arg.get("help", "")),
                    format_arg_details(arg),
                )
                for arg in ArgSpec.normalize(args_def, strict=False)  # type: ignore[arg-type]
            ]
        except ConfigValidationError as error:
            if suppress_errors:
                return []
            cls._enrich_config_error(error, args_def, task_name)
            raise

    @staticmethod
    def _enrich_config_error(
        error: ConfigValidationError, args_def: ArgsDef, task_name: str = ""
    ):
        if isinstance(error.index, int):
            if isinstance(args_def, list):
                item = args_def[error.index]
                if arg_name := (isinstance(item, dict) and item.get("name")):
                    arg_ref = arg_name
                else:
                    arg_ref = error.index
            elif arg_name := tuple(args_def.keys())[error.index]:
                arg_ref = arg_name
            else:
                arg_ref = error.index
            error.context = f"Invalid argument {arg_ref!r} declared"
        if task_name:
            error.task_name = task_name

    def build_parser(self, env: TaskEnv, program_name: str) -> ArgumentParser:
        import argparse

        parser = argparse.ArgumentParser(
            prog=f"{program_name} {self._task_name}",
            add_help=False,
            allow_abbrev=False,
        )
        for arg in self._args:
            parser.add_argument(
                *arg.options,
                **self._get_argument_params(arg, env),
            )
        return parser

    def _get_argument_params(self, arg: ArgSpec, env: TaskEnv):
        # For non-boolean args argparse's default stays empty (absent -> None),
        # and the configured default is resolved, converted to the arg type and
        # applied in `_apply_defaults`, only when the arg wasn't given. This
        # avoids argparse reporting an invalid default as a CLI usage error,
        # and action="extend" prepending a default onto the user's values.
        result = {
            "default": None,
            "help": arg.get("help", ""),
        }

        required = arg.get("required", False)
        multiple = arg.get("multiple", False)
        arg_type = str(arg.get("type"))

        if multiple:
            # An exact count (multiple = N) is enforced by _validate_exact_count
            result["nargs"] = "+" if required else "*"
            result["action"] = "extend"

        if arg.get("positional", False):
            if not multiple and not required:
                result["nargs"] = "?"
        else:
            result["dest"] = arg.name
            result["required"] = required

        if arg.choices is not None:
            result["choices"] = arg.choices

        if arg_type == "boolean":
            if isinstance(default := arg.get("default"), str):
                default = env.fill_template(default)
            try:
                coerced_default = (
                    _coerce_bool(default) if default is not None else False
                )
            except ConfigValidationError as error:
                error.context = f"Invalid default for argument {arg.name!r}"
                error.task_name = self._task_name
                raise
            if coerced_default:
                result["action"] = "store_false"
                result["default"] = True
            else:
                result["action"] = "store_true"
                result["default"] = False
        else:
            result["type"] = arg_types.get(arg_type, str)

        return result

    def parse(self, args: Sequence[str], env: TaskEnv, program_name: str):
        error_stream = (
            self._io.error_output
            if self._io.verbosity > -3
            else cast("IO[str]", os.devnull)
        )
        parser = self.build_parser(env, program_name)
        with redirect_stderr(error_stream):
            try:
                parsed_args = vars(parser.parse_args(args))
                self._validate_exact_count(parsed_args, parser)
                self._apply_defaults(parsed_args, env)
            except SystemExit as error:
                raise ExecutionError(
                    f"Invalid arguments for task {self._task_name!r}"
                ) from error

        # Ensure positional args are still exposed by name even if they were parsed
        # with alternate identifiers (via positional alias or stripped underscore)
        for arg in self._args:
            if arg.positional and (dest := arg.options[0]) != arg.name:
                parsed_args[arg.name] = parsed_args[dest]
                del parsed_args[dest]
        # args named with dash case are converted to snake case before being exposed
        return {name.replace("-", "_"): value for name, value in parsed_args.items()}

    def _validate_exact_count(self, parsed_args: dict, parser: ArgumentParser) -> None:
        """
        Enforce the "exactly N values" rule for args declared with
        ``multiple = N``. argparse can't express this constraint across
        repeated flag occurrences, so it's checked here after parsing.

        Calls ``parser.error(...)`` on a mismatch, which prints a
        ``poe <task>: error: ...`` message in argparse's own style and
        raises ``SystemExit`` — caught by the caller and reraised as
        :class:`ExecutionError`.
        """
        for arg in self._args:
            multi = arg.multiple
            # `bool` is a subclass of `int`, so guard against multiple=True
            # being treated as multiple=1 here.
            if not isinstance(multi, int) or isinstance(multi, bool):
                continue
            # dest is `arg.name` for option args (set in `_get_argument_params`)
            # and the first entry of `options` for positionals (argparse default).
            key = arg.options[0] if arg.positional else arg.name
            value = parsed_args.get(key)
            if value is None or (arg.positional and value == []):
                continue
            if len(value) != multi:
                parser.error(
                    f"argument {arg.options[0]}: expected {multi} values,"
                    f" got {len(value)}"
                )

    def _apply_defaults(self, parsed_args: dict[str, Any], env: TaskEnv) -> None:
        """
        Apply the configured default of every non-boolean arg that was absent,
        and surface every ``multiple`` arg as a list.
        """
        for arg in self._args:
            if arg.type == "boolean":
                # argparse applies boolean defaults (see _get_argument_params)
                continue
            # dest is `arg.name` for option args and `arg.options[0]` for
            # positionals, matching `_validate_exact_count`.
            key = arg.options[0] if arg.positional else arg.name
            value = parsed_args.get(key)
            if value is not None and not (arg.positional and value == []):
                # An omitted arg arrives as None, except an omitted positional
                # arg with multiple=True, which arrives as []
                continue
            default = self._resolve_default(arg, env)
            if arg.multiple:
                parsed_args[key] = [] if default is None else [default]
            else:
                parsed_args[key] = default

    def _resolve_default(self, arg: ArgSpec, env: TaskEnv) -> Any:
        """
        Resolve the configured default of a non-boolean arg: fill templates and
        convert the result to the arg type.
        """
        if (default := arg.get("default")) is None:
            return None
        if isinstance(default, str):
            default = env.fill_template(default)
        try:
            return _convert_default(default, arg.type)
        except ConfigValidationError as error:
            error.context = f"Invalid default for argument {arg.name!r}"
            error.task_name = self._task_name
            raise

    def get_env_overrides(self, values: Mapping[str, Any]) -> dict[str, str]:
        """
        Get explicitly configured boolean strings without changing typed values.
        Empty strings are retained, and templates are not expanded.
        """
        result = {}
        for arg in self._args:
            if arg.type != "boolean":
                continue
            name = arg.name.replace("-", "_")
            if (
                string_value := arg.true_string if values[name] else arg.false_string
            ) is not None:
                result[name] = string_value
        return result

    def format_argv(self, values: Mapping[str, Any], env: TaskEnv) -> list[str]:
        """
        Re-emit parsed argument values as CLI tokens — the inverse of
        :meth:`parse`. Used to forward declared args (with defaults already
        applied by the parser) into a subprocess that does its own CLI
        parsing, e.g. ``python -m some_module``.

        Conventions: positionals are emitted in declared order; option args
        use the first entry of their ``options`` list as the flag name;
        boolean flags are emitted iff the resolved value differs from the
        declared default (i.e. the user provided the flag on the CLI);
        multi-value args are emitted space-separated, matching argparse's
        ``nargs="+"`` style.
        """

        result: list[str] = []
        for arg in self._args:
            name = arg.name.replace("-", "_")
            if name not in values:
                continue
            value = values[name]

            if arg.type == "boolean":
                raw_default = arg.get("default")
                if isinstance(raw_default, str):
                    raw_default = env.fill_template(raw_default)
                try:
                    default_bool = (
                        _coerce_bool(raw_default) if raw_default is not None else False
                    )
                except ConfigValidationError as error:
                    error.context = f"Invalid default for argument {arg.name!r}"
                    error.task_name = self._task_name
                    raise
                if value != default_bool:
                    result.append(arg.options[0])
                continue

            if arg.positional:
                if arg.multiple:
                    result.extend(str(item) for item in value)
                elif value is not None:
                    result.append(str(value))
                continue

            flag = arg.options[0]
            if arg.multiple:
                if value:
                    result.append(flag)
                    result.extend(str(item) for item in value)
            elif value is not None:
                result.append(flag)
                result.append(str(value))

        return result


_BOOL_TRUE_LITERALS = frozenset({"t", "true", "1"})
_BOOL_FALSE_LITERALS = frozenset({"f", "false", "0", ""})


def _coerce_bool(value: Any) -> bool:
    """
    Coerce a config-supplied value to a real bool.

    Accepts Python bools as-is, and a small set of case-insensitive string
    literals (stripped of surrounding whitespace): ``t``/``true``/``1`` for
    True and ``f``/``false``/``0``/``""`` for False. Anything else raises
    ``ConfigValidationError``.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _BOOL_TRUE_LITERALS:
            return True
        if normalized in _BOOL_FALSE_LITERALS:
            return False
    raise ConfigValidationError(
        f"Cannot interpret {value!r} as a boolean — expected a boolean or one of "
        "'true'/'1'/'t' or 'false'/'0'/'f'/'' (case-insensitive)"
    )


def _convert_default(value: Any, arg_type: str) -> Any:
    """
    Convert a config-supplied default to the type of a non-boolean argument, as
    argparse would convert a value given on the command line.

    Booleans are never accepted for numeric types, and an integer arg only
    accepts a float default with no fractional part. Anything that can't be
    converted raises ``ConfigValidationError``.
    """
    if arg_type == "string":
        return str(value)

    if arg_type == "integer":
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
        description = "an integer"

    else:
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        description = "a float"

    raise ConfigValidationError(f"Cannot interpret {value!r} as {description}")
