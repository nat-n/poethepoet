import json
import shutil

import pytest


@pytest.mark.parametrize("default", [False, True])
@pytest.mark.parametrize("toggle", [False, True])
@pytest.mark.parametrize(
    ("options", "true_value", "false_value"),
    [
        ('true_string = "yes"', "yes", None),
        ('false_string = "no"', "True", "no"),
        ('true_string = "yes", false_string = "no"', "yes", "no"),
        ('true_string = "", false_string = ""', "", ""),
        (
            'true_string = "${TEXT}", false_string = "$TEXT"',
            "${TEXT}",
            "$TEXT",
        ),
    ],
)
def test_boolean_strings_preserve_typed_values(
    run_poe, temp_pyproject, default, toggle, options, true_value, false_value
):
    options_config = options.replace(", ", "\n")
    project = temp_pyproject(f"""
        [tool.poe.tasks.inspect]
        expr = "(type(flag).__name__, flag, __import__('os').environ.get('flag'))"
        env = {{ flag = "inherited", TEXT = "expanded" }}
        [[tool.poe.tasks.inspect.args]]
        name = "flag"
        type = "boolean"
        default = {str(default).lower()}
        {options_config}
        """)
    result = run_poe("inspect", *(("--flag",) if toggle else ()), cwd=project)
    expected_bool = default != toggle
    expected_string = true_value if expected_bool else false_value
    assert result.code == 0, result.capture + result.stderr
    assert result.stdout.strip() == repr(("bool", expected_bool, expected_string))


@pytest.mark.parametrize("toggle", [False, True])
def test_boolean_strings_command_expansion(run_poe, temp_pyproject, toggle):
    project = temp_pyproject("""
        [tool.poe.tasks.greet]
        cmd = '''poe_test_echo "${greeting_flag}" "${greeting_flag:+alternate}"
                              "${greeting_flag:-fallback}"'''
        [[tool.poe.tasks.greet.args]]
        name = "greeting-flag"
        type = "boolean"
        true_string = "hello there!"
        false_string = "hi there!"
        """)
    result = run_poe("greet", *(("--greeting-flag",) if toggle else ()), cwd=project)
    greeting = "hello there!" if toggle else "hi there!"
    assert result.code == 0, result.capture + result.stderr
    assert result.stdout == f"{greeting} alternate {greeting}\n"


@pytest.mark.parametrize("toggle", [False, True])
def test_boolean_strings_private_args(run_poe, temp_pyproject, toggle):
    project = temp_pyproject("""
        [tool.poe.tasks.inspect]
        cmd = '''python
            -c "import os, sys; print((sys.argv[1], os.getenv('_flag')))"
            "${_flag}"'''
        [[tool.poe.tasks.inspect.args]]
        name = "_flag"
        type = "boolean"
        true_string = "yes"
        false_string = "no"
        """)
    result = run_poe("inspect", *(("--flag",) if toggle else ()), cwd=project)
    assert result.code == 0, result.capture + result.stderr
    assert result.stdout.strip() == repr(("yes" if toggle else "no", None))


@pytest.mark.parametrize("default", [False, True])
@pytest.mark.parametrize("toggle", [False, True])
@pytest.mark.parametrize("name", ["flag", "my-flag"])
@pytest.mark.parametrize("env_default", [False, True])
def test_boolean_strings_module_flag_forwarding(
    run_poe, temp_pyproject, default, toggle, name, env_default
):
    env_name = name.replace("-", "_")
    default_config = '"${' + env_name + '}"' if env_default else str(default).lower()
    project = temp_pyproject(f"""
        [tool.poe.tasks.inspect]
        script = "probe"
        env = {{ {env_name} = "{str(default).lower()}" }}
        [[tool.poe.tasks.inspect.args]]
        name = "{name}"
        type = "boolean"
        default = {default_config}
        true_string = "yes"
        false_string = "no"
        """)
    (project / "probe.py").write_text(
        f"import os, sys\nprint(repr((sys.argv[1:], os.environ[{env_name!r}])))\n"
    )
    result = run_poe("inspect", *((f"--{name}",) if toggle else ()), cwd=project)
    assert result.code == 0, result.capture + result.stderr
    assert result.stdout.strip() == repr(
        ([f"--{name}"] if toggle else [], "yes" if default != toggle else "no")
    )


@pytest.mark.parametrize("toggle", [False, True])
def test_boolean_strings_composition(run_poe, toggle):
    result = run_poe(
        "inspect", *(("--flag",) if toggle else ()), project="boolean_strings"
    )
    assert result.code == 0, result.capture + result.stderr
    expected = "yes" if toggle else "no"
    assert result.stdout.splitlines() == [
        repr((toggle, expected)),
        repr((toggle, expected)),
        "child-no",
    ]


@pytest.mark.parametrize("default", [False, True])
@pytest.mark.parametrize("child_toggle", [False, True])
@pytest.mark.parametrize("parent_toggle", [False, True])
@pytest.mark.parametrize("custom_strings", [False, True])
def test_module_child_preserves_parsed_boolean_default(
    run_poe, temp_pyproject, default, child_toggle, parent_toggle, custom_strings
):
    # Child defaults currently resolve against context.env before parent args
    # are inherited. Forwarding must use that original default, even though the
    # module's environment now contains the parent's string representation.
    child_invocation = "child --child-flag" if child_toggle else "child"
    string_options = (
        'true_string = "yes", false_string = "no"' if custom_strings else ""
    )
    project = temp_pyproject(f"""
        [tool.poe.tasks.parent]
        sequence = [{{ ref = "{child_invocation}" }}]
        args = [{{ name = "FLAG", type = "boolean", {string_options} }}]

        [tool.poe.tasks.child]
        script = "probe"
        args = [{{ name = "child-flag", type = "boolean", default = "${{FLAG}}" }}]
        """)
    (project / "probe.py").write_text(
        "import os, sys\n"
        "print((sys.argv[1:], os.getenv('FLAG'), os.getenv('child_flag')))\n"
    )

    result = run_poe(
        "parent",
        *(("--FLAG",) if parent_toggle else ()),
        cwd=project,
        env={"FLAG": str(default).lower()},
    )
    parent_string = (
        ("yes" if parent_toggle else "no")
        if custom_strings
        else ("True" if parent_toggle else None)
    )
    assert result.code == 0, result.capture + result.stderr
    assert result.stdout.strip() == repr(
        (
            ["--child-flag"] if child_toggle else [],
            parent_string,
            "True" if default != child_toggle else None,
        )
    )


@pytest.mark.skipif(not shutil.which("bash"), reason="bash is not available")
@pytest.mark.parametrize("toggle", [False, True])
def test_boolean_strings_shell_expansion(run_poe, temp_pyproject, toggle):
    project = temp_pyproject("""
        [tool.poe.tasks.inspect]
        shell = 'echo "${flag}|${flag:+alternate}|${flag:-fallback}"'
        interpreter = "bash"
        [[tool.poe.tasks.inspect.args]]
        name = "flag"
        type = "boolean"
        true_string = "yes"
        false_string = "no"
        """)
    result = run_poe("inspect", *(("--flag",) if toggle else ()), cwd=project)
    expected = "yes" if toggle else "no"
    assert result.code == 0, result.capture + result.stderr
    assert result.stdout == f"{expected}|alternate|{expected}\n"


@pytest.mark.parametrize("toggle", [False, True])
def test_boolean_strings_empty_expansion(run_poe, toggle):
    result = run_poe(
        "empty", *(("--flag",) if toggle else ()), project="boolean_strings"
    )
    assert result.code == 0, result.capture + result.stderr
    assert result.stdout == "fallback\n"


@pytest.mark.parametrize("option", ["true_string", "false_string"])
@pytest.mark.parametrize("arg_type", [None, "string", "integer", "float"])
def test_boolean_strings_require_boolean_type(
    run_poe, temp_pyproject, option, arg_type
):
    type_config = f'type = "{arg_type}",' if arg_type else ""
    project = temp_pyproject(f"""
        [tool.poe.tasks.bad]
        cmd = "poe_test_echo unexpected"
        args = [{{ name = "flag", {type_config} {option} = "" }}]
        """)
    result = run_poe("bad", cwd=project)
    assert result.code != 0
    assert f"Option {option!r} requires argument type 'boolean'" in result.capture


@pytest.mark.parametrize("option", ["true_string", "false_string"])
@pytest.mark.parametrize("value", [True, 1, ["yes"]])
def test_boolean_strings_require_string_values(run_poe, temp_pyproject, option, value):
    project = temp_pyproject(f"""
        [tool.poe.tasks.bad]
        cmd = "poe_test_echo unexpected"
        args = [{{ name = "flag", type = "boolean", {option} = {json.dumps(value)} }}]
        """)
    result = run_poe("bad", cwd=project)
    assert result.code != 0
    assert option in result.capture
    assert "str" in result.capture
    assert "Unrecognized option" not in result.capture
