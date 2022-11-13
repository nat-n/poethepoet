from typing import Any, Dict, Optional, Sequence, Type

from ..exceptions import PoeException
from ..virtualenv import Virtualenv
from .base import PoeExecutor


class VirtualenvExecutor(PoeExecutor):
    """
    A poe task executor implementation that executes inside an arbitrary virtualenv
    """

    __key__ = "virtualenv"
    __options__: Dict[str, Type] = {"location": str}

    def execute(
        self, cmd: Sequence[str], input: Optional[bytes] = None, use_exec: bool = False
    ) -> int:
        """
        Execute the given cmd as a subprocess inside the configured virtualenv
        """
        venv = self._resolve_virtualenv()

        return self._execute_cmd(
            (venv.resolve_executable(cmd[0]), *cmd[1:]),
            input=input,
            env=venv.get_env_vars(self.env.to_dict()),
            use_exec=use_exec,
        )

    def _resolve_virtualenv(self) -> Virtualenv:
        if "location" in self.options:
            venv = Virtualenv(
                self.context.project_dir.joinpath(self.options["location"])
            )
            if venv.valid():
                return venv
            raise PoeException(
                f"Could not find valid virtualenv at configured location: {venv.path}"
            )

        venv = Virtualenv(self.context.project_dir.joinpath("venv"))
        if venv.valid():
            return venv

        hidden_venv = Virtualenv(self.context.project_dir.joinpath(".venv"))
        if hidden_venv.valid():
            return hidden_venv

        raise PoeException(
            f"Could not find valid virtualenv at either of: {venv.path} or "
            f"{hidden_venv.path}"
        )

    @classmethod
    def validate_executor_config(cls, config: Dict[str, Any]) -> Optional[str]:
        """
        Validate that location is a string if given and no other options are given.
        """
        if "location" in config and not isinstance(config["location"], str):
            return f"The location option virtualenv executor must be a string not: {config['location']!r}"
        extra_options = set(config.keys()) - {"type", "location"}
        if extra_options:
            return f"Unexpected keys for executor config: {extra_options!r}"
        return None
