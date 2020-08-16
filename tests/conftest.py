from collections import namedtuple
from io import StringIO
import os
from pathlib import Path
from poethepoet.app import PoeThePoet
import pytest
from subprocess import PIPE, Popen
import sys
from tempfile import TemporaryDirectory
import tomlkit
from typing import Any, List, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_TOML = PROJECT_ROOT.joinpath("pyproject.toml")


@pytest.fixture
def is_windows():
    return sys.platform == "win32"


@pytest.fixture
def pyproject():
    with PROJECT_TOML.open("r") as toml_file:
        return tomlkit.parse(toml_file.read())


@pytest.fixture
def poe_project_path():
    return PROJECT_ROOT


@pytest.fixture
def dummy_project_path():
    return PROJECT_ROOT.joinpath("tests", "fixtures", "dummy_project")


@pytest.fixture
def scripts_project_path():
    return PROJECT_ROOT.joinpath("tests", "fixtures", "scripts_project")


@pytest.fixture(scope="function")
def temp_file(tmp_path):
    # not using NamedTemporaryFile here because it doesn't work on windows
    tmpfilepath = tmp_path / "tmp_test_file"
    tmpfilepath.touch()
    yield tmpfilepath


PoeRunResult = namedtuple("PoeRunResult", ("code", "capture", "stdout", "stderr"))


@pytest.fixture(scope="function")
def run_poe_subproc(dummy_project_path, temp_file, tmp_path, is_windows):
    coverage_setup = (
        "from coverage import Coverage;"
        fr'Coverage(data_file=r\"{PROJECT_ROOT.joinpath(".coverage")}\").start();'
    )
    shell_cmd_template = (
        'python -c "'
        "{coverage_setup}"
        "import tomlkit;"
        "from poethepoet.app import PoeThePoet;"
        "from pathlib import Path;"
        r"poe = PoeThePoet(cwd=r\"{cwd}\", config={config}, output={output});"
        "poe([{run_args}]);"
        '"'
    )

    def run_poe_subproc(
        *run_args: str,
        cwd: str = dummy_project_path,
        config: Optional[Mapping[str, Any]] = None,
        coverage: bool = not is_windows,
    ) -> str:
        if config is not None:
            config_path = tmp_path.joinpath("tmp_test_config_file")
            with config_path.open("w+") as config_file:
                toml.dump(config, config_file)
                config_file.seek(0)
            config_arg = fr"tomlkit.parse(open(r\"{config_path}\", \"r\").read())"
        else:
            config_arg = "None"

        shell_cmd = shell_cmd_template.format(
            coverage_setup=(coverage_setup if coverage else ""),
            cwd=cwd,
            config=config_arg,
            run_args=",".join(f'r\\"{arg}\\"' for arg in run_args),
            output=fr"open(r\"{temp_file}\", \"w\")",
        )

        env = dict(os.environ)
        if coverage:
            env["COVERAGE_PROCESS_START"] = str(PROJECT_TOML)

        poeproc = Popen(shell_cmd, shell=True, stdout=PIPE, stderr=PIPE, env=env)
        task_out, task_err = poeproc.communicate()

        with temp_file.open("rb") as output_file:
            captured_output = output_file.read().decode().replace("\r\n", "\n")

        result = PoeRunResult(
            code=poeproc.returncode,
            capture=captured_output,
            stdout=task_out.decode().replace("\r\n", "\n"),
            stderr=task_err.decode().replace("\r\n", "\n"),
        )
        print(result)  # when a test fails this is usually useful to debug
        return result

    return run_poe_subproc


@pytest.fixture(scope="function")
def run_poe(capsys, dummy_project_path):
    def run_poe(
        *run_args: str,
        cwd: str = dummy_project_path,
        config: Optional[Mapping[str, Any]] = None,
    ) -> str:
        output_capture = StringIO()
        poe = PoeThePoet(cwd=cwd, config=config, output=output_capture)
        result = poe(run_args)
        output_capture.seek(0)
        return PoeRunResult(result, output_capture.read(), *capsys.readouterr())

    return run_poe


@pytest.fixture
def esc_prefix(is_windows):
    """
    When executing on windows it's not necessary to escape the $ for variables
    """
    if is_windows:
        return ""
    return "\\"


@pytest.fixture(scope="function")
def run_poe_main(capsys, dummy_project_path):
    def run_poe_main(
        *cli_args: str,
        cwd: str = dummy_project_path,
        config: Optional[Mapping[str, Any]] = None,
    ) -> str:
        from poethepoet import main

        prev_cwd = os.getcwd()
        os.chdir(cwd)
        sys.argv = ("poe", *cli_args)
        result = main()
        os.chdir(prev_cwd)
        return PoeRunResult(result, "", *capsys.readouterr())

    return run_poe_main
