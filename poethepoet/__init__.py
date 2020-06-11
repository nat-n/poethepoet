from .__version__ import __version__
from .app import PoeThePoet


def main() -> int:
    from pathlib import Path
    import sys

    app = PoeThePoet(cwd=Path(".").resolve(), output=sys.stdout)
    result = app(cli_args=sys.argv[1:])
    raise SystemExit(result)
