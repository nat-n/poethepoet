# ruff: noqa: E501
"""
Tests for PowerShell shell completion.

This module tests the PowerShell completion script generation.
"""

import shutil
import subprocess

import pytest


def _powershell_is_available() -> bool:
    """Check if PowerShell is actually available and functional."""
    # Check both pwsh (PowerShell Core) and powershell (Windows PowerShell)
    for cmd in ("pwsh", "powershell"):
        if shutil.which(cmd) is not None:
            try:
                proc = subprocess.run(
                    [cmd, "-NoProfile", "-Command", "$PSVersionTable"],
                    capture_output=True,
                    timeout=10,
                )
                if proc.returncode == 0:
                    return True
            except (subprocess.TimeoutExpired, OSError):
                continue
    return False


def _get_powershell_cmd() -> str:
    """Get the available PowerShell command (pwsh or powershell)."""
    for cmd in ("pwsh", "powershell"):
        if shutil.which(cmd) is not None:
            return cmd
    return "pwsh"


def test_powershell_completion(run_poe_main):
    result = run_poe_main("_powershell_completion")
    # some lines to stdout and none for stderr
    assert len(result.stdout.split("\n")) > 5
    assert result.stderr == ""
    assert "Error: Unrecognised task" not in result.stdout


class TestPowerShellCompletionScript:
    """Regression tests for PowerShell completion script structure."""

    def test_has_global_options(self, run_poe_main):
        """Verify script includes global options."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have global options array
        assert "$script:PoeGlobalOptions" in script
        assert "-h" in script
        assert "--help" in script
        assert "--version" in script
        assert "-C" in script
        assert "--directory" in script

    def test_has_options_with_values(self, run_poe_main):
        """Verify script tracks options that take values."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have array of options that take values
        assert "$script:PoeOptionsWithValues" in script
        # -C, --directory, --root, -e, --executor should take values
        assert "-C" in script
        assert "--directory" in script

    def test_has_target_path_detection(self, run_poe_main):
        """Verify script detects -C/--directory/--root."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have Get-PoeTargetPath function
        assert "Get-PoeTargetPath" in script
        # Should check for directory options
        assert "-C" in script
        assert "--directory" in script
        assert "--root" in script

    def test_has_current_task_detection(self, run_poe_main):
        """Verify script detects current task from command line."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have Get-PoeCurrentTask function
        assert "Get-PoeCurrentTask" in script
        # Should return first non-option word
        assert "return $word" in script

    def test_has_task_args_completion(self, run_poe_main):
        """Verify script calls _describe_task_args for task arguments."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have Get-PoeTaskArgs function
        assert "Get-PoeTaskArgs" in script
        # Should call _describe_task_args
        assert "_describe_task_args" in script
        assert "$TaskName" in script

    def test_has_task_list_function(self, run_poe_main):
        """Verify script has function to list tasks."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have Get-PoeTasks function
        assert "Get-PoeTasks" in script
        # Should call _list_tasks
        assert "_list_tasks" in script

    def test_has_used_options_tracking(self, run_poe_main):
        """Verify script tracks already-used options."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have Get-UsedOptions function
        assert "Get-UsedOptions" in script

    def test_has_argument_completer_registration(self, run_poe_main):
        """Verify script registers argument completer."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should use Register-ArgumentCompleter
        assert "Register-ArgumentCompleter" in script
        assert "-CommandName" in script
        assert "-Native" in script
        assert "-ScriptBlock" in script

    def test_completes_global_options(self, run_poe_main):
        """Verify script completes global options when word starts with -."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should check if word starts with -
        assert "StartsWith('-')" in script
        # Should offer global options
        assert "PoeGlobalOptions" in script

    def test_completes_task_names(self, run_poe_main):
        """Verify script completes task names."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should call Get-PoeTasks
        assert "Get-PoeTasks" in script
        # Should output CompletionResult for tasks
        assert "CompletionResult" in script
        assert "'Command'" in script

    def test_completes_task_options(self, run_poe_main):
        """Verify script completes task-specific options."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should call Get-PoeTaskArgs
        assert "Get-PoeTaskArgs" in script
        # Should parse options from output
        assert "Options" in script

    def test_handles_boolean_flags(self, run_poe_main):
        """Verify script handles boolean type from _describe_task_args."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should detect boolean args
        assert "boolean" in script

    def test_handles_choices(self, run_poe_main):
        """Verify script handles choices from _describe_task_args."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should parse choices field
        assert "Choices" in script

    def test_has_directory_completion(self, run_poe_main):
        """Verify script provides directory completion for -C."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should handle -C/--directory with directory completion
        assert "-Directory" in script or "Get-ChildItem" in script

    def test_has_executor_completion(self, run_poe_main):
        """Verify script provides executor completion."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should offer executor choices
        assert "auto" in script
        assert "poetry" in script
        assert "simple" in script
        assert "uv" in script
        assert "virtualenv" in script

    def test_has_file_completion_fallback(self, run_poe_main):
        """Verify script falls back to file completion."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should have Get-ChildItem for file completion
        assert "Get-ChildItem" in script

    def test_filters_used_options(self, run_poe_main):
        """Verify script filters out already-used options."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should track and filter used options
        assert "usedGroups" in script or "usedOpts" in script

    def test_handles_positional_args(self, run_poe_main):
        """Verify script handles positional arguments."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should track positional argument index
        assert "positional" in script.lower()

    def test_completion_result_types(self, run_poe_main):
        """Verify script uses correct CompletionResult types."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Should use appropriate completion result types
        assert "'Command'" in script  # for tasks
        assert "'ParameterName'" in script  # for options
        assert "'ParameterValue'" in script  # for values


class TestPowerShellCompletionGracefulFailure:
    """Tests for graceful failure when no config exists."""

    def test_graceful_failure_no_config(self, run_poe_main, tmp_path):
        """Completion should fail gracefully when no config exists."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = run_poe_main("_list_tasks", str(empty_dir))

        # Should not crash or raise, just return empty or minimal output
        assert "Traceback" not in result.stderr
        assert "Error" not in result.stderr


class TestPowerShellCompletionCustomName:
    """Tests for custom command name in completion script."""

    def test_custom_name_in_script(self, run_poe_main):
        """Verify custom name is used throughout the script."""
        result = run_poe_main("_powershell_completion", "mypoe")
        script = result.stdout

        # Should use custom name in Register-ArgumentCompleter
        assert "-CommandName mypoe" in script
        # Should use custom name in comments
        assert "PowerShell completion for mypoe" in script
        # Should use custom name in enable instructions
        assert "mypoe _powershell_completion" in script
        # Should use custom name in _list_tasks calls
        assert "& mypoe _list_tasks" in script


class TestPowerShellCompletionSpecialTaskNames:
    """Tests for tasks with special characters in their names.

    Poe task names can match: r"^\\w[\\w\\d\\-\\_\\+\\:]*$"
    The PowerShell script uses shared builtins (_list_tasks, _describe_task_args)
    which are tested elsewhere, but we verify the script doesn't break with special names.
    """

    def test_script_generates_without_error(self, run_poe_main, projects):
        """Script should generate without error for projects with special task names."""
        scripts_path = str(projects["scripts"])
        result = run_poe_main("_powershell_completion", cwd=scripts_path)

        assert result.code == 0
        assert len(result.stdout.split("\n")) > 5
        assert result.stderr == ""


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellCompletionSyntax:
    """Validate that the generated PowerShell completion script has valid syntax."""

    def test_powershell_completion_syntax(self, run_poe_main):
        """Validate that the generated PowerShell script has valid syntax."""
        result = run_poe_main("_powershell_completion")
        assert result.code == 0

        ps_cmd = _get_powershell_cmd()
        # Use -NoProfile to avoid loading user profile, just parse the script
        # $null = <script> loads and parses without executing side effects
        proc = subprocess.run(
            [
                ps_cmd,
                "-NoProfile",
                "-Command",
                f"$null = [scriptblock]::Create(@'\n{result.stdout}\n'@)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"PowerShell syntax error:\n{proc.stderr}"


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellCompletionIntegration:
    """Real integration tests using actual PowerShell."""

    def test_powershell_script_loads(self, run_poe_main, tmp_path):
        """Verify the script can be loaded in PowerShell without error."""
        script = run_poe_main("_powershell_completion").stdout

        # Write script to file
        script_file = tmp_path / "completion.ps1"
        script_file.write_text(script)

        ps_cmd = _get_powershell_cmd()
        # Test that the script can be dot-sourced
        proc = subprocess.run(
            [
                ps_cmd,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f". '{script_file}'",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0, f"PowerShell error: {proc.stderr}"

    def test_powershell_functions_exist(self, run_poe_main, tmp_path):
        """Verify helper functions are defined after loading script."""
        script = run_poe_main("_powershell_completion").stdout

        # Write script to file
        script_file = tmp_path / "completion.ps1"
        script_file.write_text(script)

        ps_cmd = _get_powershell_cmd()
        # Load script and check for functions
        test_script = f"""
        . '{script_file}'
        $funcs = @(
            'Get-PoeTargetPath',
            'Get-PoeCurrentTask',
            'Get-PoeTaskArgs',
            'Get-PoeTasks',
            'Get-UsedOptions'
        )
        foreach ($f in $funcs) {{
            if (-not (Get-Command $f -CommandType Function -ErrorAction SilentlyContinue)) {{
                Write-Error "Missing function: $f"
                exit 1
            }}
        }}
        Write-Output "All functions exist"
        """

        proc = subprocess.run(
            [
                ps_cmd,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                test_script,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0, f"PowerShell error: {proc.stderr}"
        assert "All functions exist" in proc.stdout

    def test_powershell_global_options_defined(self, run_poe_main, tmp_path):
        """Verify global options array is properly defined."""
        script = run_poe_main("_powershell_completion").stdout

        # Write script to file
        script_file = tmp_path / "completion.ps1"
        script_file.write_text(script)

        ps_cmd = _get_powershell_cmd()
        test_script = f"""
        . '{script_file}'
        if ($script:PoeGlobalOptions.Count -eq 0) {{
            Write-Error "PoeGlobalOptions is empty"
            exit 1
        }}
        if ('-h' -notin $script:PoeGlobalOptions) {{
            Write-Error "-h not in global options"
            exit 1
        }}
        Write-Output "Global options OK"
        """

        proc = subprocess.run(
            [
                ps_cmd,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                test_script,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0, f"PowerShell error: {proc.stderr}"
        assert "Global options OK" in proc.stdout
