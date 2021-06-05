from glob import glob
import re
import shlex
from typing import (
    Dict,
    MutableMapping,
    Sequence,
    Type,
    TYPE_CHECKING,
)
from .base import PoeTask

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
    __options__: Dict[str, Type] = {}

    def _handle_run(
        self,
        context: "RunContext",
        extra_args: Sequence[str],
        env: MutableMapping[str, str],
    ) -> int:
        env, has_named_args = self._add_named_args_to_env(extra_args, env)
        if has_named_args:
            # If named arguments are defined then it doesn't make sense to pass extra
            # args to the command, because they've already been parsed
            cmd = self._resolve_args(context, env)
        else:
            cmd = (*self._resolve_args(context, env), *extra_args)
        self._print_action(" ".join(cmd), context.dry)
        return context.get_executor(self.invocation, env, self.options).execute(cmd)

    def _add_named_args_to_env(
        self, extra_args: Sequence[str], env: MutableMapping[str, str]
    ):
        named_args = self.parse_named_args(extra_args)
        if named_args is None:
            return env, False
        return dict(env, **named_args), bool(named_args)

    def _resolve_args(
        self, context: "RunContext", env: MutableMapping[str, str],
    ):
        # Parse shell command tokens and check if they're quoted
        if self._is_windows:
            cmd_tokens = (
                (compat_token, bool(_QUOTED_TOKEN_PATTERN.match(compat_token)))
                for compat_token in shlex.split(
                    self._resolve_envvars(self.content, env),
                    posix=False,
                    comments=True,
                )
            )
        else:
            cmd_tokens = (
                (posix_token, bool(_QUOTED_TOKEN_PATTERN.match(compat_token)))
                for (posix_token, compat_token) in zip(
                    shlex.split(
                        self._resolve_envvars(self.content, env),
                        posix=True,
                        comments=True,
                    ),
                    shlex.split(
                        self._resolve_envvars(self.content, env),
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
