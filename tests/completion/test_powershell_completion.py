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

    def test_no_file_completion_for_freeform_options(self, run_poe_main):
        """Verify options without choices don't fall back to file completion."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # When an option has no choices, it should just return early
        # rather than offering file completion (which isn't helpful for text args)
        # The fix changes the "fall through to file completion" to just "return"
        assert "# No choices - don't offer completions for free-form text" in script

    def test_positional_args_array_wrapped(self, run_poe_main):
        """Verify positional args collection is wrapped in @() for array safety."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # Where-Object returns a single item directly (not as array) when only
        # one match exists. This causes .Count to return hashtable key count (2)
        # instead of array length (1). The fix wraps in @() to ensure array.
        assert "$positionalArgs = @($taskArgs | Where-Object" in script

    def test_prevword_calculation_handles_empty_completion(self, run_poe_main):
        """Verify $prevWord calculation handles empty $wordToComplete correctly."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        # When $wordToComplete is empty (user pressed Tab after a space),
        # $commandAst.CommandElements doesn't include a placeholder for it.
        # So $words[-2] points to the wrong element. The fix uses $words[-1]
        # when $wordToComplete is empty.
        assert "if ($wordToComplete -eq '' -and $words.Count -ge 1)" in script
        assert "$words[-1]" in script

    def test_has_global_option_exclusions(self, run_poe_main):
        """Verify script includes PoeGlobalOptionExclusions hashtable."""
        result = run_poe_main("_powershell_completion")
        script = result.stdout

        assert "$script:PoeGlobalOptionExclusions" in script
        # Should have entries for key options
        assert "'-h'" in script
        assert "'-v'" in script
        assert "'-X'" in script
        assert "'--ansi'" in script


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


def _run_ps_test(run_poe_main, tmp_path, test_commands, mock_poe_func=None):
    """Run PowerShell commands with the completion script loaded and return subprocess result.

    Generates the completion script, writes it to a temp file, dot-sources it,
    optionally overrides `poe` with a mock function, then runs test_commands.
    """
    script = run_poe_main("_powershell_completion").stdout
    script_file = tmp_path / "completion.ps1"
    script_file.write_text(script)

    ps_cmd = _get_powershell_cmd()
    parts = [f". '{script_file}'"]
    if mock_poe_func:
        parts.append(mock_poe_func)
    parts.append(test_commands)

    return subprocess.run(
        [
            ps_cmd,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "\n".join(parts),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellGetPoeTargetPath:
    """Test Get-PoeTargetPath function directly in PowerShell."""

    def test_c_flag(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTargetPath -Words @('poe', '-C', '/mypath', 'task1')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "/mypath" in proc.stdout.strip()

    def test_directory_flag(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTargetPath -Words @('poe', '--directory', '/other/path', 'task1')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "/other/path" in proc.stdout.strip()

    def test_root_flag(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTargetPath -Words @('poe', '--root', '/root/path', 'task1')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "/root/path" in proc.stdout.strip()

    def test_no_directory_option(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTargetPath -Words @('poe', 'task1')
            if ($null -eq $r) { Write-Output 'NULL' } else { Write-Output $r }
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "NULL"

    def test_c_at_end_no_value(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTargetPath -Words @('poe', '-C')
            if ($null -eq $r) { Write-Output 'NULL' } else { Write-Output $r }
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "NULL"

    def test_first_directory_wins(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTargetPath -Words @('poe', '-C', '/first', '--directory', '/second')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "/first" in proc.stdout.strip()

    def test_directory_interleaved_with_options(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTargetPath -Words @('poe', '-v', '--directory', '/mydir', 'task1')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "/mydir" in proc.stdout.strip()


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellGetPoeCurrentTask:
    """Test Get-PoeCurrentTask function directly in PowerShell."""

    def test_simple_task(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', 'mytask')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "mytask"

    def test_task_after_c_flag(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', '-C', '/path', 'mytask')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "mytask"

    def test_task_after_boolean_flag(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', '-v', 'mytask')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "mytask"

    def test_task_after_option_with_value(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', '-e', 'poetry', 'mytask')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "mytask"

    def test_no_task_all_options(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', '-v', '--help')
            if ($null -eq $r) { Write-Output 'NULL' } else { Write-Output $r }
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "NULL"

    def test_task_with_dashes(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', 'my-task')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "my-task"

    def test_task_with_colons(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', 'ns:task')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "ns:task"

    def test_task_with_plus(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeCurrentTask -Words @('poe', 'task+extra')
            Write-Output $r
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "task+extra"


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellGetUsedOptions:
    """Test Get-UsedOptions function directly in PowerShell."""

    def test_single_used_option(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-UsedOptions -Words @('poe', 'mytask', '--greeting', 'hello') -TaskPosition 1
            Write-Output ($r.Keys -join ',')
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "--greeting" in proc.stdout.strip()

    def test_multiple_used_options(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-UsedOptions -Words @('poe', 'mytask', '--greeting', 'hello', '-n', '5') -TaskPosition 1
            $keys = $r.Keys | Sort-Object
            Write-Output ($keys -join ',')
        """,
        )
        assert proc.returncode == 0, proc.stderr
        output = proc.stdout.strip()
        assert "--greeting" in output
        assert "-n" in output

    def test_no_options_used(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-UsedOptions -Words @('poe', 'mytask', 'arg1') -TaskPosition 1
            Write-Output "COUNT:$($r.Count)"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:0" in proc.stdout.strip()

    def test_short_form_tracking(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-UsedOptions -Words @('poe', 'mytask', '-g', 'hello') -TaskPosition 1
            Write-Output ($r.Keys -join ',')
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "-g" in proc.stdout.strip()


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellGetPoeTasks:
    """Test Get-PoeTasks function with mocked poe command."""

    def test_basic_list(self, run_poe_main, tmp_path):
        mock = 'function poe { Write-Output "greet echo build test" }'
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTasks
            Write-Output ($r -join ',')
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        tasks = proc.stdout.strip().split(",")
        assert "greet" in tasks
        assert "echo" in tasks
        assert "build" in tasks
        assert "test" in tasks

    def test_empty_output(self, run_poe_main, tmp_path):
        mock = "function poe { }"
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTasks)
            Write-Output "COUNT:$($r.Count)"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:0" in proc.stdout.strip()

    def test_mock_throws(self, run_poe_main, tmp_path):
        mock = 'function poe { throw "error" }'
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTasks)
            Write-Output "COUNT:$($r.Count)"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:0" in proc.stdout.strip()

    def test_special_chars_in_names(self, run_poe_main, tmp_path):
        mock = 'function poe { Write-Output "my-task ns:task task+extra" }'
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTasks
            Write-Output ($r -join ',')
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        tasks = proc.stdout.strip().split(",")
        assert "my-task" in tasks
        assert "ns:task" in tasks
        assert "task+extra" in tasks

    def test_target_path_forwarded(self, run_poe_main, tmp_path):
        mock = """function poe {
    if ($args[1] -eq '/custom/path') {
        Write-Output "pathed-task"
    } else {
        Write-Output "default-task"
    }
}"""
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTasks -TargetPath '/custom/path'
            Write-Output ($r -join ',')
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "pathed-task" in proc.stdout.strip()


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellGetPoeTaskArgs:
    """Test Get-PoeTaskArgs function with mocked poe command."""

    def test_single_arg(self, run_poe_main, tmp_path):
        mock = (
            'function poe { Write-Output "--greeting,-g`tstring`tGreeting message`t_" }'
        )
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTaskArgs -TaskName 'greet')
            Write-Output "COUNT:$($r.Count)"
            Write-Output "OPTS:$($r[0].Options -join ',')"
            Write-Output "TYPE:$($r[0].Type)"
            Write-Output "HELP:$($r[0].Help)"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:1" in proc.stdout
        assert "OPTS:--greeting,-g" in proc.stdout
        assert "TYPE:string" in proc.stdout
        assert "HELP:Greeting message" in proc.stdout

    def test_multiple_args(self, run_poe_main, tmp_path):
        mock = 'function poe { Write-Output "--greeting,-g`tstring`tGreeting`t_`n--count,-n`tinteger`tCount`t_" }'
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTaskArgs -TaskName 'greet')
            Write-Output "COUNT:$($r.Count)"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:2" in proc.stdout

    def test_args_with_choices(self, run_poe_main, tmp_path):
        mock = 'function poe { Write-Output "--format,-f`tstring`tOutput format`tjson xml csv" }'
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTaskArgs -TaskName 'export')
            Write-Output "CHOICES:$($r[0].Choices -join ',')"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "CHOICES:json,xml,csv" in proc.stdout

    def test_positional_arg(self, run_poe_main, tmp_path):
        mock = 'function poe { Write-Output "name`tpositional`tThe name`t_" }'
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTaskArgs -TaskName 'greet')
            Write-Output "TYPE:$($r[0].Type)"
            Write-Output "OPTS:$($r[0].Options -join ',')"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "TYPE:positional" in proc.stdout
        assert "OPTS:name" in proc.stdout

    def test_empty_task_name(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTaskArgs -TaskName ''
            Write-Output "COUNT:$($r.Count)"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:0" in proc.stdout

    def test_target_path_forwarded(self, run_poe_main, tmp_path):
        mock = """function poe {
    if ($args[2] -eq '/custom/path') {
        Write-Output "--pathed`tstring`tPathed arg`t_"
    } else {
        Write-Output "--default`tstring`tDefault arg`t_"
    }
}"""
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTaskArgs -TaskName 'mytask' -TargetPath '/custom/path')
            Write-Output "OPTS:$($r[0].Options -join ',')"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "OPTS:--pathed" in proc.stdout


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellUsedOptionGroupFiltering:
    """Test the usedGroups logic that filters already-used option groups."""

    def test_short_form_excludes_long(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--greeting', '-g'); Type = 'string'; Help = 'Greeting'; Choices = @() }
                @{ Options = @('--count', '-n'); Type = 'integer'; Help = 'Count'; Choices = @() }
            )
            $words = @('poe', 'greet', '-g', 'hello')
            $usedGroups = @{}
            foreach ($word in $words) {
                if (-not $word.StartsWith('-')) { continue }
                foreach ($arg in $taskArgs) {
                    if ($word -in $arg.Options) {
                        foreach ($opt in $arg.Options) {
                            $usedGroups[$opt] = $true
                        }
                    }
                }
            }
            Write-Output "GREETING:$($usedGroups.ContainsKey('--greeting'))"
            Write-Output "G:$($usedGroups.ContainsKey('-g'))"
            Write-Output "COUNT:$($usedGroups.ContainsKey('--count'))"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "GREETING:True" in proc.stdout
        assert "G:True" in proc.stdout
        assert "COUNT:False" in proc.stdout

    def test_long_form_excludes_short(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--greeting', '-g'); Type = 'string'; Help = 'Greeting'; Choices = @() }
            )
            $words = @('poe', 'greet', '--greeting', 'hello')
            $usedGroups = @{}
            foreach ($word in $words) {
                if (-not $word.StartsWith('-')) { continue }
                foreach ($arg in $taskArgs) {
                    if ($word -in $arg.Options) {
                        foreach ($opt in $arg.Options) {
                            $usedGroups[$opt] = $true
                        }
                    }
                }
            }
            Write-Output "G:$($usedGroups.ContainsKey('-g'))"
            Write-Output "GREETING:$($usedGroups.ContainsKey('--greeting'))"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "G:True" in proc.stdout
        assert "GREETING:True" in proc.stdout

    def test_unrelated_options_unaffected(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--greeting', '-g'); Type = 'string'; Help = 'Greeting'; Choices = @() }
                @{ Options = @('--count', '-n'); Type = 'integer'; Help = 'Count'; Choices = @() }
            )
            $words = @('poe', 'greet', '-g', 'hello')
            $usedGroups = @{}
            foreach ($word in $words) {
                if (-not $word.StartsWith('-')) { continue }
                foreach ($arg in $taskArgs) {
                    if ($word -in $arg.Options) {
                        foreach ($opt in $arg.Options) {
                            $usedGroups[$opt] = $true
                        }
                    }
                }
            }
            Write-Output "N:$($usedGroups.ContainsKey('-n'))"
            Write-Output "COUNT:$($usedGroups.ContainsKey('--count'))"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "N:False" in proc.stdout
        assert "COUNT:False" in proc.stdout

    def test_multiple_groups_used(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--greeting', '-g'); Type = 'string'; Help = 'Greeting'; Choices = @() }
                @{ Options = @('--count', '-n'); Type = 'integer'; Help = 'Count'; Choices = @() }
                @{ Options = @('--verbose'); Type = 'boolean'; Help = 'Verbose'; Choices = @() }
            )
            $words = @('poe', 'greet', '-g', 'hello', '-n', '5')
            $usedGroups = @{}
            foreach ($word in $words) {
                if (-not $word.StartsWith('-')) { continue }
                foreach ($arg in $taskArgs) {
                    if ($word -in $arg.Options) {
                        foreach ($opt in $arg.Options) {
                            $usedGroups[$opt] = $true
                        }
                    }
                }
            }
            Write-Output "GREETING:$($usedGroups.ContainsKey('--greeting'))"
            Write-Output "COUNT:$($usedGroups.ContainsKey('--count'))"
            Write-Output "VERBOSE:$($usedGroups.ContainsKey('--verbose'))"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "GREETING:True" in proc.stdout
        assert "COUNT:True" in proc.stdout
        assert "VERBOSE:False" in proc.stdout


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellOptionValueCompletion:
    """Test option value completion logic."""

    def test_choices_offered_for_string_option(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--format', '-f'); Type = 'string'; Help = 'Format'; Choices = @('json', 'xml', 'csv') }
            )
            $prevWord = '--format'
            $curWord = ''
            $results = @()
            foreach ($arg in $taskArgs) {
                if ($prevWord -in $arg.Options) {
                    if ($arg.Type -eq 'boolean') { break }
                    if ($arg.Choices.Count -gt 0) {
                        $results = @($arg.Choices | Where-Object { $_ -like "$curWord*" })
                    }
                }
            }
            Write-Output ($results -join ',')
        """,
        )
        assert proc.returncode == 0, proc.stderr
        choices = proc.stdout.strip().split(",")
        assert "json" in choices
        assert "xml" in choices
        assert "csv" in choices

    def test_boolean_flag_no_value_completion(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--verbose', '-v'); Type = 'boolean'; Help = 'Verbose'; Choices = @() }
            )
            $prevWord = '--verbose'
            $matched = $false
            foreach ($arg in $taskArgs) {
                if ($prevWord -in $arg.Options) {
                    if ($arg.Type -eq 'boolean') {
                        $matched = $true
                        break
                    }
                }
            }
            Write-Output "BOOLEAN_BREAK:$matched"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "BOOLEAN_BREAK:True" in proc.stdout

    def test_no_choices_returns_early(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--name', '-n'); Type = 'string'; Help = 'Name'; Choices = @() }
            )
            $prevWord = '--name'
            $hasChoices = $false
            foreach ($arg in $taskArgs) {
                if ($prevWord -in $arg.Options) {
                    if ($arg.Choices.Count -gt 0) {
                        $hasChoices = $true
                    }
                }
            }
            Write-Output "HAS_CHOICES:$hasChoices"
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "HAS_CHOICES:False" in proc.stdout

    def test_partial_choice_filtering(self, run_poe_main, tmp_path):
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--format', '-f'); Type = 'string'; Help = 'Format'; Choices = @('json', 'xml', 'csv') }
            )
            $prevWord = '--format'
            $curWord = 'j'
            $results = @()
            foreach ($arg in $taskArgs) {
                if ($prevWord -in $arg.Options) {
                    if ($arg.Choices.Count -gt 0) {
                        $results = @($arg.Choices | Where-Object { $_ -like "$curWord*" })
                    }
                }
            }
            Write-Output ($results -join ',')
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "json"


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellPositionalArgCompletion:
    """Test positional argument index tracking logic."""

    def test_first_positional_with_choices(self, run_poe_main, tmp_path):
        # Simulates: poe pick-flavor <TAB>
        # When wordToComplete is '', CommandElements doesn't include the empty token
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('flavor'); Type = 'positional'; Help = 'Flavor'; Choices = @('vanilla', 'chocolate', 'strawberry') }
            )
            $words = @('poe', 'pick-flavor')
            $wordToComplete = ''
            $taskPosition = 1
            $positionalIndex = 0
            for ($i = $taskPosition + 1; $i -lt $words.Count; $i++) {
                $word = $words[$i]
                if ($word.StartsWith('-')) {
                    $isValuedOpt = $false
                    foreach ($arg in $taskArgs) {
                        if ($word -in $arg.Options -and $arg.Type -ne 'boolean') {
                            $isValuedOpt = $true; break
                        }
                    }
                    if ($isValuedOpt) { $i++ }
                    continue
                }
                if ($i -lt ($words.Count - 1) -or $wordToComplete -eq '') {
                    $positionalIndex++
                }
            }
            $positionalArgs = @($taskArgs | Where-Object { $_.Type -eq 'positional' })
            if ($positionalIndex -lt $positionalArgs.Count) {
                Write-Output "CHOICES:$($positionalArgs[$positionalIndex].Choices -join ',')"
            } else {
                Write-Output "NO_MATCH"
            }
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "CHOICES:vanilla,chocolate,strawberry" in proc.stdout

    def test_positional_after_option_with_value(self, run_poe_main, tmp_path):
        # Simulates: poe pick-flavor --count 5 <TAB>
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('--count', '-n'); Type = 'integer'; Help = 'Count'; Choices = @() }
                @{ Options = @('flavor'); Type = 'positional'; Help = 'Flavor'; Choices = @('vanilla', 'chocolate') }
            )
            $words = @('poe', 'pick-flavor', '--count', '5')
            $wordToComplete = ''
            $taskPosition = 1
            $positionalIndex = 0
            for ($i = $taskPosition + 1; $i -lt $words.Count; $i++) {
                $word = $words[$i]
                if ($word.StartsWith('-')) {
                    $isValuedOpt = $false
                    foreach ($arg in $taskArgs) {
                        if ($word -in $arg.Options -and $arg.Type -ne 'boolean') {
                            $isValuedOpt = $true; break
                        }
                    }
                    if ($isValuedOpt) { $i++ }
                    continue
                }
                if ($i -lt ($words.Count - 1) -or $wordToComplete -eq '') {
                    $positionalIndex++
                }
            }
            Write-Output "INDEX:$positionalIndex"
            $positionalArgs = @($taskArgs | Where-Object { $_.Type -eq 'positional' })
            if ($positionalIndex -lt $positionalArgs.Count) {
                Write-Output "CHOICES:$($positionalArgs[$positionalIndex].Choices -join ',')"
            }
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "INDEX:0" in proc.stdout
        assert "CHOICES:vanilla,chocolate" in proc.stdout

    def test_positional_without_choices(self, run_poe_main, tmp_path):
        # Simulates: poe greet <TAB> where name is positional with no choices
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $taskArgs = @(
                @{ Options = @('name'); Type = 'positional'; Help = 'Name'; Choices = @() }
            )
            $words = @('poe', 'greet')
            $wordToComplete = ''
            $taskPosition = 1
            $positionalIndex = 0
            for ($i = $taskPosition + 1; $i -lt $words.Count; $i++) {
                $word = $words[$i]
                if ($word.StartsWith('-')) { continue }
                if ($i -lt ($words.Count - 1) -or $wordToComplete -eq '') {
                    $positionalIndex++
                }
            }
            $positionalArgs = @($taskArgs | Where-Object { $_.Type -eq 'positional' })
            if ($positionalIndex -lt $positionalArgs.Count -and $positionalArgs[$positionalIndex].Choices.Count -gt 0) {
                Write-Output "HAS_CHOICES"
            } else {
                Write-Output "NO_CHOICES"
            }
        """,
        )
        assert proc.returncode == 0, proc.stderr
        assert "NO_CHOICES" in proc.stdout


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellGracefulFailure:
    """Test graceful failure handling in PowerShell."""

    def test_describe_task_args_returns_empty(self, run_poe_main, tmp_path):
        mock = "function poe { }"
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = Get-PoeTaskArgs -TaskName 'nonexistent'
            Write-Output "COUNT:$($r.Count)"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:0" in proc.stdout

    def test_list_tasks_returns_empty(self, run_poe_main, tmp_path):
        mock = "function poe { }"
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $r = @(Get-PoeTasks)
            Write-Output "COUNT:$($r.Count)"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "COUNT:0" in proc.stdout

    def test_mock_poe_throws_exception(self, run_poe_main, tmp_path):
        mock = "function poe { throw 'Something went wrong' }"
        proc = _run_ps_test(
            run_poe_main,
            tmp_path,
            """
            $tasks = @(Get-PoeTasks)
            $argsResult = Get-PoeTaskArgs -TaskName 'sometask'
            Write-Output "TASKS:$($tasks.Count)"
            Write-Output "ARGS:$($argsResult.Count)"
        """,
            mock_poe_func=mock,
        )
        assert proc.returncode == 0, proc.stderr
        assert "TASKS:0" in proc.stdout
        assert "ARGS:0" in proc.stdout


@pytest.mark.skipif(
    not _powershell_is_available(), reason="PowerShell not available or not functional"
)
class TestPowerShellGlobalOptionFiltering:
    """Test that already-used global options are filtered from completions."""

    def _build_exclusion_test(
        self, run_poe_main, tmp_path, words_ps, assert_excluded, assert_available
    ):
        """Helper: dot-source script, build $excludedGlobalOpts from $words, check results."""
        words_str = ", ".join(f"'{w}'" for w in words_ps)
        excluded_checks = "\n".join(
            f"            Write-Output \"EXCL:{opt}:$($excludedGlobalOpts.ContainsKey('{opt}'))\""
            for opt in assert_excluded
        )
        available_checks = "\n".join(
            f"            Write-Output \"AVAIL:{opt}:$(-not $excludedGlobalOpts.ContainsKey('{opt}'))\""
            for opt in assert_available
        )
        test_commands = f"""
            $words = @({words_str})
            $excludedGlobalOpts = @{{}}
            for ($j = 1; $j -lt $words.Count; $j++) {{
                $w = $words[$j]
                if ($w.StartsWith('-') -and $script:PoeGlobalOptionExclusions.ContainsKey($w)) {{
                    foreach ($ex in $script:PoeGlobalOptionExclusions[$w]) {{
                        $excludedGlobalOpts[$ex] = $true
                    }}
                }}
            }}
{excluded_checks}
{available_checks}
        """
        proc = _run_ps_test(run_poe_main, tmp_path, test_commands)
        assert proc.returncode == 0, f"PowerShell error: {proc.stderr}"
        for opt in assert_excluded:
            assert (
                f"EXCL:{opt}:True" in proc.stdout
            ), f"Expected {opt} to be excluded, output: {proc.stdout}"
        for opt in assert_available:
            assert (
                f"AVAIL:{opt}:True" in proc.stdout
            ), f"Expected {opt} to be available, output: {proc.stdout}"

    def test_nonrepeatable_excludes_identity_group(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "-d"],
            assert_excluded=["-d", "--dry-run"],
            assert_available=["-v", "-C"],
        )

    def test_long_form_excludes_short(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "--dry-run"],
            assert_excluded=["-d", "--dry-run"],
            assert_available=[],
        )

    def test_short_form_excludes_long(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "-C", "/path"],
            assert_excluded=["-C", "--directory"],
            assert_available=[],
        )

    def test_repeatable_count_not_self_excluded(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "-v"],
            assert_excluded=["-q", "--quiet"],
            assert_available=["-v", "--verbose"],
        )

    def test_repeatable_append_not_excluded(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "-X", "k=v"],
            assert_excluded=[],
            assert_available=["-X", "--executor-opt"],
        )

    def test_ansi_excludes_no_ansi(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "--ansi"],
            assert_excluded=["--ansi", "--no-ansi"],
            assert_available=[],
        )

    def test_no_ansi_excludes_ansi(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "--no-ansi"],
            assert_excluded=["--ansi", "--no-ansi"],
            assert_available=[],
        )

    def test_quiet_excludes_verbose(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "--quiet"],
            assert_excluded=["-v", "--verbose"],
            assert_available=["-q", "--quiet"],
        )

    def test_multiple_cumulative(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe", "-v", "-d"],
            assert_excluded=["-q", "--quiet", "-d", "--dry-run"],
            assert_available=["-v", "--verbose", "-C"],
        )

    def test_no_options_nothing_excluded(self, run_poe_main, tmp_path):
        self._build_exclusion_test(
            run_poe_main,
            tmp_path,
            words_ps=["poe"],
            assert_excluded=[],
            assert_available=[
                "-h",
                "--help",
                "-v",
                "--verbose",
                "-d",
                "--dry-run",
                "-C",
                "--directory",
                "-X",
            ],
        )
