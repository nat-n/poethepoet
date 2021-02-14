import argparse
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from ..config import PoeConfig

ArgParams = Dict[str, Any]
ArgsDef = Union[List[str], List[ArgParams], Dict[str, ArgParams]]
arg_param_schema: Dict[str, Union[Type, Tuple[Type, ...]]] = {
    "default": (str, int, float, bool),
    "help": str,
    "name": str,
    "options": (list, tuple),
    "required": bool,
}


class PoeTaskArgs:
    _args: Tuple[ArgParams, ...]

    def __init__(self, args_def: ArgsDef):
        self._args = self._normalize_args_def(args_def)

    @staticmethod
    def _normalize_args_def(args_def: ArgsDef):
        """
        args_def can be defined as a dictionary of ArgParams, or a list of strings, or
        ArgParams. Here we normalize it to a list of ArgParams, assuming that it has
        already been validated.
        """
        result = []
        if isinstance(args_def, list):
            for item in args_def:
                if isinstance(item, str):
                    result.append({"name": item, "options": (f"--{item}",)})
                else:
                    result.append(
                        dict(
                            item,
                            options=tuple(
                                item.get("options", (f"--{item.get('name')}",))
                            ),
                        )
                    )
        else:
            for name, params in args_def.items():
                result.append(
                    dict(
                        params,
                        name=name,
                        options=tuple(params.get("options", (f"--{name}",))),
                    )
                )
        return result

    @classmethod
    def get_help_content(
        cls, args_def: Optional[ArgsDef]
    ) -> List[Tuple[Tuple[str, ...], str]]:
        if args_def is None:
            return []
        args = cls._normalize_args_def(args_def)
        return [(arg["options"], arg.get("help", "")) for arg in args]

    @classmethod
    def validate_def(cls, task_name: str, args_def: ArgsDef) -> Optional[str]:
        arg_names: Set[str] = set()
        if isinstance(args_def, list):
            for item in args_def:
                # can be a list of strings (just arg name) or ArgConfig dictionaries
                if isinstance(item, str):
                    arg_name = item
                elif isinstance(item, dict):
                    arg_name = item.get("name", "")
                    error = cls._validate_params(item, arg_name, task_name)
                    if error:
                        return error
                else:
                    return f"Arg {item!r} of task {task_name!r} has invlaid type"
                error = cls._validate_name(arg_name, task_name, arg_names)
                if error:
                    return error
        elif isinstance(args_def, dict):
            for arg_name, params in args_def.items():
                error = cls._validate_name(arg_name, task_name, arg_names)
                if error:
                    return error
                if "name" in params:
                    return (
                        f"Unexpected 'name' option for arg {arg_name!r} of task "
                        f"{task_name!r}"
                    )
                error = cls._validate_params(params, arg_name, task_name)
                if error:
                    return error
        return None

    @classmethod
    def _validate_params(
        cls, params: ArgParams, arg_name: str, task_name: str
    ) -> Optional[str]:
        for param, value in params.items():
            if param not in arg_param_schema:
                return (
                    f"Invalid option {param!r} for arg {arg_name!r} of task "
                    f"{task_name!r}"
                )
            if not isinstance(value, arg_param_schema[param]):
                return (
                    f"Invalid value for option {param!r} of arg {arg_name!r} of"
                    f" task {task_name!r}"
                )
        return None

    @classmethod
    def _validate_name(
        cls, name: Any, task_name: str, arg_names: Set[str]
    ) -> Optional[str]:
        if not isinstance(name, str):
            return f"Arg name {name!r} of task {task_name!r} should be a string"
        if not name.isidentifier():
            return (
                f"Arg name {name!r} of task {task_name!r} is not a valid " "identifier"
            )
        if name in arg_names:
            return f"Duplicate arg name {name!r} for task {task_name!r}"
        arg_names.add(name)
        return None

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        for arg in self._args:
            parser.add_argument(
                *arg["options"],
                default=arg.get("default", ""),
                dest=arg["name"],
                required=arg.get("required", False),
                help=arg.get("help", ""),
            )
        return parser

    def parse(self, extra_args: Sequence[str]):
        return vars(self.build_parser().parse_args(extra_args))
