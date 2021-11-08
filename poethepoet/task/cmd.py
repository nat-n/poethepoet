from glob import glob
import re
import shlex
from typing import (
    Dict,
    Mapping,
    Sequence,
    Type,
    Tuple,
    TYPE_CHECKING,
    Union,
)
from .base import PoeTask
from ..helpers.env import resolve_envvars

if TYPE_CHECKING:
    from ..config import PoeConfig
    from ..context import RunContext

_GLOBCHARS_PATTERN = re.compile(r".*[\*\?\[]")
_QUOTED_TOKEN_PATTERN = re.compile(r"(^\".*\"$|^'.*'$)")


class CmdTask(PoeTask):
    """
    A task consisting of a reference to a shell command
    """

    content: str

    __key__ = "cmd"
    __options__: Dict[str, Union[Type, Tuple[Type, ...]]] = {}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: Mapping[str, str],
    ) -> int:
        env, has_named_args = self.add_named_args_to_env(env)
        if has_named_args:
            # If named arguments are defined then it doesn't make sense to pass extra
            # args to the command, because they've already been parsed
            cmd = self._resolve_args(context, env)
        else:
            cmd = (*self._resolve_args(context, env), *extra_args)
        self._print_action(" ".join(cmd), context.dry)
        return context.get_executor(self.invocation, env, self.options).execute(cmd)

    def _resolve_args(self, context: "RunContext", env: Mapping[str, str]):
        # Parse shell command tokens and check if they're quoted
        if self._is_windows:
            cmd_tokens = (
                (compat_token, bool(_QUOTED_TOKEN_PATTERN.match(compat_token)))
                for compat_token in shlex.split(
                    resolve_envvars(self.content, env),
                    posix=False,
                    comments=True,
                )
            )
        else:
            cmd_tokens = (
                (posix_token, bool(_QUOTED_TOKEN_PATTERN.match(compat_token)))
                for (posix_token, compat_token) in zip(
                    shlex.split(
                        resolve_envvars(self.content, env),
                        posix=True,
                        comments=True,
                    ),
                    shlex.split(
                        resolve_envvars(self.content, env),
                        posix=False,
                        comments=True,
                    ),
                )
            )
        # Resolve any unquoted glob pattern paths
        result = []
        for (cmd_token, is_quoted) in cmd_tokens:
            if not is_quoted and _GLOBCHARS_PATTERN.match(cmd_token):
                # looks like a glob path so resolve it
                result.extend(glob(cmd_token, recursive=True))
            else:
                result.append(cmd_token)
        return result
