import os
import re
import shutil
import sys
import time
import venv
from collections.abc import Mapping
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from subprocess import PIPE, Popen
from typing import Any, NamedTuple, Optional

import pytest
import virtualenv

from poethepoet.app import PoeThePoet
from poethepoet.virtualenv import Virtualenv

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore[no-redef]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_TOML = PROJECT_ROOT.joinpath("pyproject.toml")


@pytest.fixture(scope="session")
def is_windows():
    return sys.platform == "win32"


@pytest.fixture(scope="session")
def pyproject():
    with PROJECT_TOML.open("rb") as toml_file:
        return tomli.load(toml_file)


@pytest.fixture(scope="session")
def poe_project_path():
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def projects():
    """
    General purpose provider of paths to test projects with the conventional layout
    """
    base_path = PROJECT_ROOT / "tests" / "fixtures"
    projects = {
        re.match(r"^([_\w]+)_project", path.name).groups()[0]: path.resolve()
        for path in base_path.glob("*_project")
    }

    projects.update(
        {
            f"{project_key}/"
            + re.match(
                rf".*?/{project_key}_project/([_\w\/]+?)(:?\/pyproject)?.toml$",
                path.as_posix(),
            ).groups()[0]: path
            for project_key, project_path in projects.items()
            for path in project_path.glob("**/*.toml")
            if "site-packages" not in str(path)
        }
    )
    return projects


@pytest.fixture(scope="session")
def low_verbosity_project_path():
    return PROJECT_ROOT.joinpath("tests", "fixtures", "low_verbosity")


@pytest.fixture(scope="session")
def high_verbosity_project_path():
    return PROJECT_ROOT.joinpath("tests", "fixtures", "high_verbosity")


@pytest.fixture
def temp_file(tmp_path):
    # not using NamedTemporaryFile here because it doesn't work on windows
    tmpfilepath = tmp_path / "tmp_test_file"
    tmpfilepath.touch()
    return tmpfilepath


class PoeRunResult(NamedTuple):
    code: int
    path: str
    capture: str
    stdout: str
    stderr: str

    def __str__(self):
        return (
            "PoeRunResult(\n"
            f"  code={self.code!r},\n"
            f"  path={self.path},\n"
            f"  capture=`{self.capture}`,\n"
            f"  stdout=`{self.stdout}`,\n"
            f"  stderr=`{self.stderr}`,\n"
            ")"
        )

    def assert_no_err(self):
        # Only stderr output allowed is from poetry creating its venv
        assert all(
            line.startswith("Creating virtualenv ") for line in self.stderr.splitlines()
        )


@pytest.fixture
def run_poe_subproc(projects, temp_file, tmp_path, is_windows):
    coverage_setup = (
        "from coverage import Coverage;"
        rf'Coverage(data_file=r\"{PROJECT_ROOT.joinpath(".coverage")}\").start();'
    )
    shell_cmd_template = (
        'python -c "'
        "{coverage_setup}"
        + (
            "import tomli;"
            # ruff: noqa: YTT204
            if sys.version_info.minor < 11
            else "import tomllib as tomli;"
        )
        + "from poethepoet.app import PoeThePoet;"
        "from pathlib import Path;"
        r"poe = PoeThePoet(cwd=r\"{cwd}\", config={config}, output={output});"
        "exit(poe([{run_args}]));"
        '"'
    )

    def run_poe_subproc(
        *run_args: str,
        cwd: Optional[str] = None,
        config: Optional[Mapping[str, Any]] = None,
        coverage: bool = not is_windows,
        env: Optional[dict[str, str]] = None,
        project: Optional[str] = None,
    ) -> PoeRunResult:
        if cwd is None:
            cwd = projects.get(project, projects["example"])

        if config is not None:
            config_path = tmp_path.joinpath("tmp_test_config_file")
            with config_path.open("w+") as config_file:
                tomli.dump(config, config_file)
                config_file.seek(0)
            config_arg = rf"tomli.load(open(r\"{config_path}\", \"rb\"))"

        else:
            config_arg = "None"

        shell_cmd = shell_cmd_template.format(
            coverage_setup=(coverage_setup if coverage else ""),
            cwd=cwd,
            config=config_arg,
            run_args=",".join(f'r\\"{arg}\\"' for arg in run_args),
            output=rf"open(r\"{temp_file}\", \"w\")",
        )

        subproc_env = dict(os.environ)
        subproc_env.pop("VIRTUAL_ENV", None)
        subproc_env.pop("POE_CWD", None)  # do not inherit this from the test
        subproc_env.pop("POE_PWD", None)  # do not inherit this from the test
        if env:
            subproc_env.update(env)

        if coverage:
            subproc_env["COVERAGE_PROCESS_START"] = str(PROJECT_TOML)

        poeproc = Popen(
            shell_cmd, shell=True, stdout=PIPE, stderr=PIPE, env=subproc_env
        )
        task_out, task_err = poeproc.communicate()

        with temp_file.open("rb") as output_file:
            captured_output = (
                output_file.read().decode(errors="ignore").replace("\r\n", "\n")
            )

        result = PoeRunResult(
            code=poeproc.returncode,
            path=cwd,
            capture=captured_output,
            stdout=task_out.decode(errors="ignore").replace("\r\n", "\n"),
            stderr=task_err.decode(errors="ignore").replace("\r\n", "\n"),
        )
        print(result)  # when a test fails this is usually useful to debug
        return result

    return run_poe_subproc


@pytest.fixture
def run_poe(capsys, projects):
    def run_poe(
        *run_args: str,
        cwd: str = projects["example"],
        config: Optional[Mapping[str, Any]] = None,
        project: Optional[str] = None,
        config_name="pyproject.toml",
        program_name="poe",
        env: Optional[Mapping[str, str]] = None,
    ) -> PoeRunResult:
        cwd = projects.get(project, cwd)
        output_capture = StringIO()
        poe = PoeThePoet(
            cwd=cwd,
            config=config,
            output=output_capture,
            config_name=config_name,
            program_name=program_name,
            env=env,
        )
        result = poe(run_args)
        output_capture.seek(0)
        return PoeRunResult(result, cwd, output_capture.read(), *capsys.readouterr())

    return run_poe


@pytest.fixture
def run_poe_main(capsys, projects):
    def run_poe_main(
        *cli_args: str,
        cwd: str = projects["example"],
        config: Optional[Mapping[str, Any]] = None,
        project: Optional[str] = None,
    ) -> PoeRunResult:
        cwd = projects.get(project, cwd)
        from poethepoet import main

        prev_cwd = os.getcwd()
        os.chdir(cwd)
        sys.argv = ("poe", *cli_args)
        result = main()
        os.chdir(prev_cwd)
        return PoeRunResult(result, cwd, "", *capsys.readouterr())

    return run_poe_main


@pytest.fixture(scope="session")
def run_poetry(use_venv, poe_project_path, version: str = "2.0.0"):
    venv_location = poe_project_path / "tests" / "temp" / "poetry_venv"

    def run_poetry(args: list[str], cwd: str, env: Optional[dict[str, str]] = None):
        venv = Virtualenv(venv_location)

        cmd = (venv.resolve_executable("python"), "-m", "poetry", *args)
        print("Poetry cmd:", cmd[0])
        poetry_proc = Popen(
            cmd,
            env=venv.get_env_vars({**os.environ, **(env or {})}),
            stdout=PIPE,
            stderr=PIPE,
            cwd=cwd,
        )
        poetry_out, poetry_err = poetry_proc.communicate()
        result = PoeRunResult(
            code=poetry_proc.returncode,
            path=cwd,
            capture="",
            stdout=poetry_out.decode(errors="ignore").replace("\r\n", "\n"),
            stderr=poetry_err.decode(errors="ignore").replace("\r\n", "\n"),
        )
        print(result)  # when a test fails this is usually useful to debug
        return result

    with use_venv(
        venv_location,
        [
            ".[poetry_plugin]",
            f"./tests/fixtures/packages/poetry-{version}-py3-none-any.whl",
        ],
        require_empty=True,
    ):
        yield run_poetry


@pytest.fixture(scope="session")
def esc_prefix(is_windows):
    """
    When executing on windows it's not necessary to escape the $ for variables
    """
    if is_windows:
        return ""
    return "\\"


@pytest.fixture(scope="session")
def install_into_virtualenv():
    def install_into_virtualenv(location: Path, contents: list[str]):
        venv = Virtualenv(location)
        Popen(
            (venv.resolve_executable("pip"), "install", *contents),
            env=venv.get_env_vars(os.environ),
            stdout=PIPE,
            stderr=PIPE,
        ).communicate(timeout=120)

    return install_into_virtualenv


@pytest.fixture(scope="session")
def use_venv(install_into_virtualenv):
    @contextmanager
    def use_venv(
        location: Path,
        contents: Optional[list[str]] = None,
        require_empty: bool = False,
    ):
        did_exist = location.is_dir()
        assert not require_empty or not did_exist, (
            f"Test requires no directory already exists at {location}, "
            "maybe try delete it and run again"
        )

        # create new venv
        venv.EnvBuilder(
            symlinks=True,
            with_pip=True,
        ).create(str(location))

        if contents:
            install_into_virtualenv(location, contents)

        yield
        # Only cleanup if we actually created it to avoid this fixture being a bit
        # dangerous
        if not did_exist:
            try_rm_dir(location)

    return use_venv


@pytest.fixture(scope="session")
def use_virtualenv(install_into_virtualenv):
    @contextmanager
    def use_virtualenv(
        location: Path,
        contents: Optional[list[str]] = None,
        require_empty: bool = False,
    ):
        did_exist = location.is_dir()
        assert not require_empty or not did_exist, (
            f"Test requires no directory already exists at {location}, "
            "maybe try delete it (via `poe clean`) and try again"
        )

        # create new virtualenv
        virtualenv.cli_run([str(location)])

        if contents:
            install_into_virtualenv(location, contents)

        yield
        # Only cleanup if we actually created it to avoid this fixture being a bit
        # dangerous
        if not did_exist:
            try_rm_dir(location)

    return use_virtualenv


def try_rm_dir(location: Path):
    try:
        shutil.rmtree(location)
    except:  # noqa: E722
        # The above sometimes files with a Permissions error in CI for Windows
        # No idea why, but maybe this will help
        print("Retrying venv cleanup")
        time.sleep(1)
        try:
            shutil.rmtree(location)
        except:  # noqa: E722
            print(
                "Cleanup failed. You might need to run `poe clean` before tests can be "
                "run again."
            )


@pytest.fixture(scope="session")
def with_virtualenv_and_venv(use_venv, use_virtualenv):
    def with_virtualenv_and_venv(
        location: Path,
        contents: Optional[list[str]] = None,
    ):
        with use_venv(location, contents, require_empty=True):
            yield

        with use_virtualenv(location, contents, require_empty=True):
            yield

    return with_virtualenv_and_venv


@pytest.fixture
def temp_pyproject(tmp_path):
    """Return function which generates pyproject.toml with the given content"""

    def generator(project_tmpl: str):
        with open(tmp_path / "pyproject.toml", "w") as fp:
            fp.write(project_tmpl)

        return tmp_path

    return generator
