"""
Tests for bash shell completion.
"""

import shutil
import subprocess

import pytest


def _bash_is_available() -> bool:
    """Check if bash is actually available and functional."""
    bash_path = shutil.which("bash")
    if bash_path is None:
        return False
    try:
        proc = subprocess.run(["bash", "--version"], capture_output=True, timeout=5)
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def test_bash_completion(run_poe_main):
    result = run_poe_main("_bash_completion")
    # some lines to stdout and none for stderr
    assert len(result.stdout.split("\n")) > 5
    assert result.stderr == ""
    assert "Error: Unrecognised task" not in result.stdout


class TestBashCompletionScript:
    """Tests for improved bash completion script."""

    def test_has_global_options(self, run_poe_main):
        """Verify script includes global options."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        # Should include common global options
        assert "-h --help" in script or '"-h" "--help"' in script
        assert "--version" in script
        assert "-C" in script
        assert "--directory" in script

    def test_extracts_target_path(self, run_poe_main):
        """Verify script extracts -C/--directory/--root."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        assert "-C|--directory|--root)" in script
        assert 'target_path="${words[i+1]}"' in script

    def test_calls_list_tasks_with_target_path(self, run_poe_main):
        """Verify _list_tasks is called with target_path."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        assert '_list_tasks "$target_path"' in script

    def test_calls_describe_task_args(self, run_poe_main):
        """Verify _describe_task_args is called for task-specific completion."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        # Uses _describe_task_args to get full arg info (opts, type, help, choices)
        assert "_describe_task_args" in script
        assert '"$current_task"' in script

    def test_completes_options_when_dash(self, run_poe_main):
        """Verify script completes options when current word starts with -."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        assert '[[ "$cur" == -* ]]' in script

    def test_parses_choices_from_describe_task_args(self, run_poe_main):
        """Verify script parses choices from _describe_task_args output."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        # Should parse tab-separated output from _describe_task_args
        assert "IFS=$'\\t'" in script
        # Should extract choices from the output
        assert "opt_choices" in script

    def test_handles_boolean_flags(self, run_poe_main):
        """Verify script handles boolean type from _describe_task_args."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        # Should detect boolean args and not expect a value
        assert "boolean" in script
        assert "is_boolean" in script

    def test_filters_used_options(self, run_poe_main):
        """Verify script filters out already-used options."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        # Should track used option forms (including equivalents)
        assert "used_forms" in script
        # Should filter them out
        assert "filtered_args" in script

    def test_root_option_not_offered(self, run_poe_main):
        """--root is deprecated (SUPPRESS) and should not be offered."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        # Find the global options line - the one that includes -h --help
        import re

        match = re.search(r'compgen -W "([^"]*-h --help[^"]*)"', script)
        global_opts = match.group(1) if match else ""

        assert "--root" not in global_opts
        assert "-C" in global_opts  # but -C should be there

    def test_handles_positional_choices(self, run_poe_main):
        """Verify script handles positional argument choices."""
        result = run_poe_main("_bash_completion")
        script = result.stdout

        # Should use _describe_task_args to get positional info
        assert "_describe_task_args" in script
        # Should track positional index
        assert "positional_index" in script
        # Should have array for positional choices
        assert "positional_choices" in script


class TestBashCompletionGracefulFailure:
    """Tests for graceful failure when no config exists."""

    def test_graceful_failure_no_config(self, run_poe_main, tmp_path):
        """Completion should fail gracefully when no config exists."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = run_poe_main("_list_tasks", str(empty_dir))

        # Should not crash or raise, just return empty or minimal output
        # The key is no uncaught exceptions or tracebacks in stderr
        assert "Traceback" not in result.stderr
        assert "Error" not in result.stderr


class TestBashCompletionSpecialTaskNames:
    """Tests for Python builtins with special task names.

    Poe task names can match: r"^\\w[\\w\\d\\-\\_\\+\\:]*$"
    These tests verify the Python side handles all valid characters.
    """

    def test_list_tasks_includes_special_names(self, run_poe_main, projects):
        """_list_tasks should include tasks with special characters."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_list_tasks", scripts_path)

        # Tasks with digits
        assert "task1" in result.stdout
        # Tasks with plus
        assert "build+test" in result.stdout
        # Tasks with colons (namespaced)
        assert "docker:build" in result.stdout
        assert "ns:sub:task" in result.stdout
        # Tasks with underscore prefix are hidden (private tasks)
        assert "_private_task" not in result.stdout
        # Tasks with mixed special chars
        assert "build_v2-fast+ci:latest" in result.stdout

        assert result.stderr == ""

    def test_describe_task_args_with_colon_task(self, run_poe_main, projects):
        """_describe_task_args should work with namespaced task names."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_describe_task_args", "docker:build", scripts_path)

        assert "--tag" in result.stdout
        assert "-t" in result.stdout
        assert result.stderr == ""

    def test_describe_task_args_with_plus_task(self, run_poe_main, projects):
        """_describe_task_args should work with plus in task name."""
        scripts_path = str(projects["scripts"])
        # build+test has no args, should return empty
        result = run_poe_main("_describe_task_args", "build+test", scripts_path)

        assert result.stdout == ""
        assert result.stderr == ""

    def test_describe_task_args_with_mixed_special_chars(self, run_poe_main, projects):
        """_describe_task_args should work with all special chars in name."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main(
            "_describe_task_args", "build_v2-fast+ci:latest", scripts_path
        )

        assert "--verbose" in result.stdout
        assert "-v" in result.stdout
        assert result.stderr == ""


class TestTaskArgsOutputFormat:
    """Contract tests for _describe_task_args output format.

    The _describe_task_args builtin is used by both bash and zsh completion scripts.
    These tests verify the output format matches the shell script expectations.
    """

    def test_describe_task_args_output_format(self, run_poe_main, projects):
        """Verify _describe_task_args output format matches shell expectations."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_describe_task_args", "flavor-picker", scripts_path)

        lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(lines) > 0, "Expected at least one argument line"

        for line in lines:
            parts = line.split("\t")
            assert len(parts) == 4, f"Expected 4 tab-separated fields: {line!r}"
            opts, arg_type, _help_text, _choices = parts
            assert opts, f"Options field should not be empty: {line!r}"
            assert arg_type in (
                "string",
                "boolean",
                "integer",
                "float",
                "positional",
            ), f"Invalid type {arg_type!r} in: {line!r}"

    def test_describe_task_args_options_comma_separated(self, run_poe_main, projects):
        """Options with multiple forms should be comma-separated."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_describe_task_args", "flavor-picker", scripts_path)

        # --flavor,-f should be comma-separated
        assert "--flavor,-f\t" in result.stdout

    def test_describe_task_args_choices_space_separated(self, run_poe_main, projects):
        """Choices should be space-separated in the 4th field."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_describe_task_args", "flavor-picker", scripts_path)

        lines = result.stdout.strip().split("\n")
        flavor_line = next(line for line in lines if "--flavor" in line)
        parts = flavor_line.split("\t")
        choices = parts[3]

        # Choices should be space-separated
        assert "vanilla" in choices
        assert "chocolate" in choices
        assert "strawberry" in choices

    def test_describe_task_args_empty_choices_placeholder(self, run_poe_main, projects):
        """Args without choices should have '_' placeholder."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_describe_task_args", "greet-full-args", scripts_path)

        lines = [line for line in result.stdout.strip().split("\n") if line]
        for line in lines:
            parts = line.split("\t")
            # All args in greet-full-args have no choices
            assert (
                parts[3] == "_"
            ), f"Expected '_' placeholder for empty choices: {line!r}"

    def test_describe_task_args_positional_type(self, run_poe_main, projects):
        """Positional args should have type 'positional'."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_describe_task_args", "flavor-picker", scripts_path)

        lines = result.stdout.strip().split("\n")
        size_line = next(line for line in lines if line.startswith("size\t"))
        parts = size_line.split("\t")

        assert parts[0] == "size"
        assert parts[1] == "positional"


@pytest.mark.skipif(
    not _bash_is_available(), reason="bash not available or not functional"
)
class TestBashCompletionIntegration:
    """Real integration tests using actual bash and poe builtins."""

    def test_bash_positional_completion_integration(
        self, run_poe_main, projects, tmp_path
    ):
        """End-to-end: bash completion with real poe builtins."""
        script = run_poe_main("_bash_completion").stdout
        scripts_path = str(projects["scripts"])

        # Write script to file to avoid quoting issues
        script_file = tmp_path / "completion.bash"
        script_file.write_text(script)

        test_script = f"""
source "{script_file}"
COMP_WORDS=(poe -C "{scripts_path}" flavor-picker "")
COMP_CWORD=4
_poe_complete
echo "${{COMPREPLY[@]}}"
"""
        result = subprocess.run(
            ["bash", "-c", test_script],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Bash error: {result.stderr}"
        # Should offer positional choices (size)
        assert (
            "small" in result.stdout
            or "medium" in result.stdout
            or "large" in result.stdout
        )

    def test_bash_option_choices_integration(self, run_poe_main, projects, tmp_path):
        """End-to-end: bash completion for option with choices."""
        script = run_poe_main("_bash_completion").stdout
        scripts_path = str(projects["scripts"])

        # Write script to file to avoid quoting issues
        script_file = tmp_path / "completion.bash"
        script_file.write_text(script)

        test_script = f"""
source "{script_file}"
COMP_WORDS=(poe -C "{scripts_path}" flavor-picker --flavor "")
COMP_CWORD=5
_poe_complete
echo "${{COMPREPLY[@]}}"
"""
        result = subprocess.run(
            ["bash", "-c", test_script],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Bash error: {result.stderr}"
        # Should offer flavor choices
        assert "vanilla" in result.stdout

    def test_bash_task_list_integration(self, run_poe_main, projects, tmp_path):
        """End-to-end: bash completion lists tasks."""
        script = run_poe_main("_bash_completion").stdout
        scripts_path = str(projects["scripts"])

        # Write script to file to avoid quoting issues
        script_file = tmp_path / "completion.bash"
        script_file.write_text(script)

        test_script = f"""
source "{script_file}"
COMP_WORDS=(poe -C "{scripts_path}" "")
COMP_CWORD=3
_poe_complete
echo "${{COMPREPLY[@]}}"
"""
        result = subprocess.run(
            ["bash", "-c", test_script],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Bash error: {result.stderr}"
        # Should list tasks
        assert "flavor-picker" in result.stdout
