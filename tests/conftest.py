from collections import namedtuple
from io import StringIO
import os
from pathlib import Path
from poethepoet import PoeThePoet
import pytest
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile
import toml
from typing import Any, List, Mapping, Optional

PROJECT_ROOT = Path(__file__).joinpath("../..").resolve()
PROJECT_TOML = PROJECT_ROOT.joinpath("pyproject.toml")


@pytest.fixture
def pyproject():
    with PROJECT_TOML.open("r") as toml_file:
        return toml.load(toml_file)


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
def tmpfile_name():
    with NamedTemporaryFile() as tmpfile:
        yield Path(tmpfile.name)


PoeRunResult = namedtuple("PoeRunResult", ("code", "capture", "stdout", "stderr"))


@pytest.fixture(scope="function")
def run_poe_subproc(dummy_project_path, tmpfile_name):
    coverage_setup = (
        "from coverage import Coverage;"
        fr'Coverage(data_file=\"{PROJECT_ROOT.joinpath(".coverage")}\").start();'
    )
    shell_cmd_template = (
        'python -c "'
        "{coverage_setup}"
        "import toml;"
        "from poethepoet import PoeThePoet;"
        "from pathlib import Path;"
        r"poe = PoeThePoet(cwd=\"{cwd}\", config={config}, output={output});"
        "poe([{run_args}]);"
        '"'
    )

    def run_poe_subproc(
        *run_args: str,
        cwd: str = dummy_project_path,
        config: Optional[Mapping[str, Any]] = None,
        coverage: bool = True,
    ) -> str:
        with NamedTemporaryFile("w+") as config_tmpfile:
            if config is not None:
                toml.dump(config, config_tmpfile)
                config_tmpfile.seek(0)
                config_arg = fr"toml.load(open(\"{config_tmpfile.name}\", \"r\"))"
            else:
                config_arg = "None"

            shell_cmd = shell_cmd_template.format(
                coverage_setup=(coverage_setup if coverage else ""),
                cwd=cwd,
                config=config_arg,
                run_args=",".join(f'\\"{arg}\\"' for arg in run_args),
                output=fr"open(\"{tmpfile_name}\", \"w\")",
            )

            env = dict(os.environ)
            if coverage:
                env["COVERAGE_PROCESS_START"] = str(PROJECT_TOML)

            poeproc = Popen(shell_cmd, shell=True, stdout=PIPE, stderr=PIPE, env=env)
            task_out, task_err = poeproc.communicate()

        with open(tmpfile_name, "rb") as output_file:
            captured_output = output_file.read().decode()

        result = PoeRunResult(
            code=poeproc.returncode,
            capture=captured_output,
            stdout=task_out.decode(),
            stderr=task_err.decode(),
        )
        print(result)  # when a test fails this is usually useful to debug
        return result

    return run_poe_subproc


@pytest.fixture(scope="function")
def run_poe(capsys, tmpfile_name, dummy_project_path):
    def run_poe(
        *run_args: str,
        cwd: str = dummy_project_path,
        config: Optional[Mapping[str, Any]] = None,
        capture=tmpfile_name,
    ) -> str:
        output_capture = StringIO()
        poe = PoeThePoet(cwd=cwd, config=config, output=output_capture)
        result = poe(run_args)
        output_capture.seek(0)
        return PoeRunResult(result, output_capture.read(), *capsys.readouterr())

    return run_poe
