import pytest


@pytest.mark.parametrize(
    ("expression", "output", "env"),
    [
        # basic parameter value expansion
        (r"$", "$", {}),
        (r"A${FOO}B", "AB", {}),
        (r"A${FOO}B", "AB", {"FOO": ""}),
        (r"A${FOO}B", "A x B", {"FOO": " x "}),
        (r"A${FOO}B", "A B", {"FOO": "   "}),
        (r"A${FOO}B", "AfooB", {"FOO": "foo"}),
        # default value operator
        (r"A${FOO:-}B", "AB", {}),
        (r"A${FOO:-bar}B", "AbarB", {}),
        (r"A${FOO:-bar}B", "AbarB", {"FOO": ""}),
        (r"A${FOO:-bar}B", "AfooB", {"FOO": "foo"}),
        # alternate value operator
        (r"A${FOO:+bar}B", "AB", {}),
        (r"A${FOO:+bar}B", "AB", {"FOO": ""}),
        (r"A${FOO:+}B", "AB", {"FOO": "foo"}),
        (r"A${FOO:+bar}B", "AbarB", {"FOO": "foo"}),
        # recursion
        (r"A${FOO:->${BAR:+ ${BAZ:- the end }<}}B", "A> the end <B", {"BAR": "X"}),
        # weird argument content
        (r"A${FOO:- !&%;#($)@}B", "A !&%;#($)@B", {}),
        (r'"A${FOO:-?.*[x]}B"', "A?.*[x]B", {}),
        (
            r"""A${FOO:-

            hey

            }B""",
            "A hey B",
            {},
        ),
    ],
)
def test_param_expansion_operations(
    expression, output, env, run_poe, temp_pyproject, tmp_path
):
    stdout_path = tmp_path / "output.txt"
    stdout_path.touch(exist_ok=True)
    project_toml = f'''
    [tool.poe.tasks.echo-expression]
    cmd = """echo {expression}"""
    capture_stdout = "{stdout_path.as_posix()}"
    '''
    project_path = temp_pyproject(project_toml)
    result = run_poe("echo-expression", cwd=project_path, env=env)

    print(project_toml)
    print("result", result)

    assert result.code == 0

    with stdout_path.open() as stdout_file:
        assert (
            stdout_file.read() == f"{output}\n"
        ), "Task output should match test parameter"
