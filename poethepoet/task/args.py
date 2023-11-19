from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

if TYPE_CHECKING:
    from argparse import ArgumentParser

    from ..env.manager import EnvVarsManager

from ..exceptions import ConfigValidationError
from ..options import PoeOptions

ArgParams = Dict[str, Any]
ArgsDef = Union[List[str], List[ArgParams], Dict[str, ArgParams]]

arg_param_schema: Dict[str, Union[Type, Tuple[Type, ...]]] = {
    "default": (str, int, float, bool),
    "help": str,
    "name": str,
    "options": (list, tuple),
    "positional": (bool, str),
    "required": bool,
    "type": str,
    "multiple": (bool, int),
}
arg_types: Dict[str, Type] = {
    "string": str,
    "float": float,
    "integer": int,
    "boolean": bool,
}


class ArgSpec(PoeOptions):
    default: Optional[Union[str, int, float, bool]] = None
    help: str = ""
    name: str
    options: Union[list, tuple]
    positional: Union[bool, str] = False
    required: bool = False
    type: Literal["string", "float", "integer", "boolean"] = "string"
    multiple: Union[bool, int] = False

    @classmethod
    def normalize(cls, args_def: ArgsDef, strict: bool = True):
        """
        Becuase arguments can be declared with different structures
        (i.e. dict or list), this function normalizes the input into a list of
        dictionaries with necessary keys.

        This is also where we do any validation that requires access to the raw
        config.
        """
        if isinstance(args_def, list):
            for item in args_def:
                if isinstance(item, str):
                    yield {"name": item, "options": (f"--{item}",)}
                elif isinstance(item, dict):
                    yield dict(
                        item,
                        options=cls._get_arg_options_list(item, strict=strict),
                    )
                elif strict:
                    raise ConfigValidationError(
                        f"Argument {item!r} has invlaid type, a string or dict is "
                        "expected"
                    )

        elif isinstance(args_def, dict):
            for name, params in args_def.items():
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
        source: Union[Mapping[str, Any], list],
        strict: bool = True,
        extra_keys: Sequence[str] = tuple(),
    ):
        """
        Override parse function to perform validations that require considering all
        argument declarations at once.
        """
        result = tuple(super().parse(source, strict, extra_keys))

        if strict:
            arg_names = set()
            positional_multiple = None
            for arg in result:
                if arg.name in arg_names:
                    raise ConfigValidationError(f"Duplicate argument name {arg.name!r}")
                arg_names.add(arg.name)

                if arg.positional:
                    if positional_multiple:
                        raise ConfigValidationError(
                            f"Only the last positional arg of task may accept"
                            f" multiple values (not {positional_multiple!r})."
                        )
                    if arg.multiple:
                        positional_multiple = arg.name

        yield from result

    @staticmethod
    def _get_arg_options_list(
        arg: ArgParams, name: Optional[str] = None, strict: bool = True
    ):
        position = arg.get("positional", False)
        name = name or arg.get("name")
        if position:
            if strict and arg.get("options"):
                raise ConfigValidationError(
                    f"Positional argument {name!r} may not declare options"
                )
            # Fill in the options param in a way that makes sesne for argparse
            if isinstance(position, str):
                return [position]
            return [name]
        return tuple(arg.get("options", (f"--{name}",)))

    def validate(self):
        try:
            return self._validate()
        except ConfigValidationError as error:
            error.context = f"Invalid argument {self.name!r} declared"
            raise

    def _validate(self):
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
                "Argument with type 'boolean' may not delcare option 'multiple'"
            )


class PoeTaskArgs:
    _args: Tuple[ArgSpec, ...]

    def __init__(self, args_def: ArgsDef, task_name: str):
        self._task_name = task_name
        self._args = self._parse_args_def(args_def)

    def _parse_args_def(self, args_def: ArgsDef):
        try:
            return tuple(ArgSpec.parse(args_def))
        except ConfigValidationError as error:
            if isinstance(error.index, int):
                if isinstance(args_def, list):
                    item = args_def[error.index]
                    if arg_name := (isinstance(item, dict) and item.get("name")):
                        arg_ref = arg_name
                elif arg_name := tuple(args_def.keys())[error.index]:
                    arg_ref = arg_name
                else:
                    arg_ref = error.index
                error.context = f"Invalid argument {arg_ref!r} declared"
            error.task_name = self._task_name
            raise

    @classmethod
    def get_help_content(
        cls, args_def: Optional[ArgsDef]
    ) -> List[Tuple[Tuple[str, ...], str, str]]:
        if args_def is None:
            return []

        def format_default(arg) -> str:
            default = arg.get("default")
            if default:
                return f"[default: {default}]"
            return ""

        return [
            (arg["options"], arg.get("help", ""), format_default(arg))
            for arg in ArgSpec.normalize(args_def, strict=False)
        ]

    def build_parser(
        self, env: "EnvVarsManager", program_name: str
    ) -> "ArgumentParser":
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

    def _get_argument_params(self, arg: ArgSpec, env: "EnvVarsManager"):
        default = arg.get("default")
        if isinstance(default, str):
            default = env.fill_template(default)

        result = {
            "default": default,
            "help": arg.get("help", ""),
        }

        required = arg.get("required", False)
        multiple = arg.get("multiple", False)
        arg_type = str(arg.get("type"))

        if multiple is True:
            if required:
                result["nargs"] = "+"
            else:
                result["nargs"] = "*"
        elif multiple and isinstance(multiple, int):
            result["nargs"] = multiple

        if arg.get("positional", False):
            if not multiple and not required:
                result["nargs"] = "?"
        else:
            result["dest"] = arg.name
            result["required"] = required

        if arg_type == "boolean":
            result["action"] = "store_false" if default else "store_true"
        else:
            result["type"] = arg_types.get(arg_type, str)

        return result

    def parse(
        self, extra_args: Sequence[str], env: "EnvVarsManager", program_name: str
    ):
        parsed_args = vars(self.build_parser(env, program_name).parse_args(extra_args))
        # Ensure positional args are still exposed by name even if they were parsed with
        # alternate identifiers
        for arg in self._args:
            if isinstance(arg.positional, str):
                parsed_args[arg.name] = parsed_args[arg.positional]
                del parsed_args[arg.positional]
        # args named with dash case are converted to snake case before being exposed
        return {name.replace("-", "_"): value for name, value in parsed_args.items()}
