from glob import glob
import re
import shlex
from typing import (
    Dict,
    Iterable,
    MutableMapping,
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
        extra_args: Iterable[str],
        env: MutableMapping[str, str],
    ) -> int:
        cmd = (*self._resolve_args(context, env), *extra_args)
        self._print_action(" ".join(cmd), context.dry)
        return context.get_executor(env, self.options.get("executor")).execute(cmd)

    def _resolve_args(
        self, context: "RunContext", env: MutableMapping[str, str],
    ):
        # Parse shell command tokens and check if they're quoted
        if self._is_windows:
            cmd_tokens = (
                (compat_token, bool(_QUOTED_TOKEN_PATTERN.match(compat_token)))
                for compat_token in shlex.split(
                    self._resolve_envvars(self.content, context, env),
                    posix=False,
                    comments=True,
                )
            )
        else:
            cmd_tokens = (
                (posix_token, bool(_QUOTED_TOKEN_PATTERN.match(compat_token)))
                for (posix_token, compat_token) in zip(
                    shlex.split(
                        self._resolve_envvars(self.content, context, env),
                        posix=True,
                        comments=True,
                    ),
                    shlex.split(
                        self._resolve_envvars(self.content, context, env),
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
