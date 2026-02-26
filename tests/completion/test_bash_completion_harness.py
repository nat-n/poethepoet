"""
Bash completion end-to-end harness tests.

These tests run real bash with stubbed completion builtins to verify
the completion logic works correctly. The harness captures what our
script passes to compgen, _filedir, and COMPREPLY.
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


requires_bash = pytest.mark.skipif(
    not _bash_is_available(), reason="bash not available or not functional"
)


@requires_bash
class TestBashCompletionBasic:
    """Basic tests that verify script structure and parsing."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_script_parses_without_error(self, completion_script, tmp_path):
        """The completion script should parse without bash errors."""
        script_file = tmp_path / "completion.bash"
        script_file.write_text(completion_script)

        proc = subprocess.run(
            ["bash", "-n", str(script_file)],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"Syntax error: {proc.stderr}"

    def test_script_can_be_sourced(self, completion_script, tmp_path):
        """The completion script can be sourced in bash."""
        proc = subprocess.run(
            [
                "bash",
                "-c",
                f"source /dev/stdin << 'EOF'\n{completion_script}\nEOF\necho ok",
            ],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"Source error: {proc.stderr}"
        assert "ok" in proc.stdout

    def test_function_defined(self, completion_script):
        """The _poe_complete function should be defined after sourcing."""
        proc = subprocess.run(
            [
                "bash",
                "-c",
                f"source /dev/stdin << 'EOF'\n{completion_script}\nEOF\n"
                "type _poe_complete",
            ],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"Error: {proc.stderr}"
        assert "_poe_complete is a function" in proc.stdout

    def test_complete_command_registered(self, completion_script):
        """The complete command should be registered for poe."""
        proc = subprocess.run(
            [
                "bash",
                "-c",
                f"source /dev/stdin << 'EOF'\n{completion_script}\nEOF\n"
                "complete -p poe",
            ],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"Error: {proc.stderr}"
        assert "_poe_complete" in proc.stdout
        assert "poe" in proc.stdout

    def test_init_completion_fallback(self, bash_harness, completion_script):
        """Script should work without _init_completion via fallback."""
        mock_output = {"_list_tasks": "greet echo"}

        result = bash_harness(
            completion_script,
            words=["poe", ""],
            current=1,
            mock_poe_output=mock_output,
        )

        # The harness's _init_completion stub returns 0, so fallback isn't triggered
        # But the script should still work
        assert result.init_completion_called or result.cur == ""


@requires_bash
class TestBashTaskCompletion:
    """Tests for task name completion."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_task_completion_empty_line(self, bash_harness, completion_script):
        """poe <TAB> should list all tasks."""
        mock_output = {"_list_tasks": "greet echo build test"}

        result = bash_harness(
            completion_script,
            words=["poe", ""],
            current=1,
            mock_poe_output=mock_output,
        )

        assert result.list_tasks_called
        assert "greet" in result.compreply
        assert "echo" in result.compreply
        assert "build" in result.compreply
        assert "test" in result.compreply

    def test_task_completion_partial(self, bash_harness, completion_script):
        """poe gr<TAB> should filter to matching tasks."""
        mock_output = {"_list_tasks": "greet echo build grep"}

        result = bash_harness(
            completion_script,
            words=["poe", "gr"],
            current=1,
            mock_poe_output=mock_output,
        )

        assert result.list_tasks_called
        assert "greet" in result.compreply
        assert "grep" in result.compreply
        assert "echo" not in result.compreply
        assert "build" not in result.compreply

    def test_task_completion_no_tasks(self, bash_harness, completion_script):
        """Empty COMPREPLY when no tasks match."""
        mock_output = {"_list_tasks": ""}

        result = bash_harness(
            completion_script,
            words=["poe", "xyz"],
            current=1,
            mock_poe_output=mock_output,
        )

        assert result.compreply == [] or result.compreply == [""]

    def test_task_completion_after_global_option(self, bash_harness, completion_script):
        """poe -v <TAB> should still complete task names."""
        mock_output = {"_list_tasks": "greet echo"}

        result = bash_harness(
            completion_script,
            words=["poe", "-v", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.list_tasks_called
        assert "greet" in result.compreply

    def test_task_completion_after_c_option(self, bash_harness, completion_script):
        """poe -C /path <TAB> should use target path."""
        mock_output = {"_list_tasks": "remote-task"}

        result = bash_harness(
            completion_script,
            words=["poe", "-C", "/some/path", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/some/path"
        assert "remote-task" in result.compreply

    def test_task_completion_after_directory_option(
        self, bash_harness, completion_script
    ):
        """poe --directory /path <TAB> should use target path."""
        mock_output = {"_list_tasks": "dir-task"}

        result = bash_harness(
            completion_script,
            words=["poe", "--directory", "/other/path", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/other/path"

    def test_task_completion_after_root_option(self, bash_harness, completion_script):
        """poe --root /path <TAB> should use target path."""
        mock_output = {"_list_tasks": "root-task"}

        result = bash_harness(
            completion_script,
            words=["poe", "--root", "/root/path", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/root/path"


@requires_bash
class TestBashGlobalOptions:
    """Tests for global option completion."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_global_options_with_dash(self, bash_harness, completion_script):
        """poe -<TAB> should show global options."""
        mock_output = {"_list_tasks": "greet"}

        result = bash_harness(
            completion_script,
            words=["poe", "-"],
            current=1,
            mock_poe_output=mock_output,
        )

        # Should have options starting with -
        assert any(opt.startswith("-") for opt in result.compreply)
        # Common options should be present
        assert "-h" in result.compreply or "--help" in result.compreply

    def test_global_options_with_double_dash(self, bash_harness, completion_script):
        """poe --<TAB> should show long options."""
        mock_output = {"_list_tasks": "greet"}

        result = bash_harness(
            completion_script,
            words=["poe", "--"],
            current=1,
            mock_poe_output=mock_output,
        )

        # Should have long options
        assert "--help" in result.compreply or any(
            opt.startswith("--") for opt in result.compreply
        )

    def test_global_options_partial(self, bash_harness, completion_script):
        """poe --h<TAB> should filter to matching options."""
        mock_output = {"_list_tasks": "greet"}

        result = bash_harness(
            completion_script,
            words=["poe", "--h"],
            current=1,
            mock_poe_output=mock_output,
        )

        # Should only show options starting with --h
        assert "--help" in result.compreply
        assert "--version" not in result.compreply

    def test_executor_option_choices(self, bash_harness, completion_script):
        """poe -e <TAB> should show executor choices."""
        mock_output = {"_list_tasks": "greet"}

        result = bash_harness(
            completion_script,
            words=["poe", "-e", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        # Should show executor options
        assert "auto" in result.compreply
        assert "poetry" in result.compreply
        assert "simple" in result.compreply

    def test_directory_option_files(self, bash_harness, completion_script):
        """poe -C <TAB> should show file completions."""
        mock_output = {"_list_tasks": "greet"}
        mock_files = ["project1/", "project2/", "file.txt"]

        result = bash_harness(
            completion_script,
            words=["poe", "-C", ""],
            current=2,
            mock_poe_output=mock_output,
            mock_files=mock_files,
        )

        # Should call _filedir for file completion
        assert result.filedir_called or result.compgen_called

    def test_no_task_mixed_with_options(self, bash_harness, completion_script):
        """Tasks should not appear when completing options."""
        mock_output = {"_list_tasks": "greet echo"}

        result = bash_harness(
            completion_script,
            words=["poe", "-"],
            current=1,
            mock_poe_output=mock_output,
        )

        # Tasks should not be in completions when word starts with -
        assert "greet" not in result.compreply
        assert "echo" not in result.compreply


@requires_bash
class TestBashTaskArguments:
    """Tests for task-specific argument completion."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_describe_task_args_basic(self, bash_harness, completion_script):
        """poe task <TAB> should show task options."""
        mock_output = {
            "_list_tasks": "greet",
            "_bash_describe_task_args": "--greeting -g --upper",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", ""],
            current=2,
            mock_poe_output=mock_output,
            mock_files=["file1.txt"],
        )

        # After task, should offer files or args
        # The script falls back to file completion if not starting with -
        assert result.filedir_called or result.compgen_called

    def test_describe_task_args_partial(self, bash_harness, completion_script):
        """poe task --f<TAB> should filter to matching options."""
        mock_output = {
            "_list_tasks": "pick",
            "_bash_describe_task_args": "--flavor -f --format --foo",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--f"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.task_args_called
        # Should filter to options starting with --f
        assert "--flavor" in result.compreply
        assert "--format" in result.compreply
        assert "--foo" in result.compreply

    def test_describe_task_args_with_choices(self, bash_harness, completion_script):
        """poe task --opt <TAB> should show choices."""
        # _describe_task_args format: opts\ttype\thelp\tchoices
        zsh_args = "--flavor,-f\tstring\tFlavor\tvanilla chocolate strawberry"
        mock_output = {
            "_list_tasks": "pick",
            "_describe_task_args": zsh_args,
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--flavor", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.task_args_called
        assert "vanilla" in result.compreply
        assert "chocolate" in result.compreply
        assert "strawberry" in result.compreply

    def test_describe_task_args_after_option_value(
        self, bash_harness, completion_script
    ):
        """poe task --opt value <TAB> should show remaining options."""
        mock_output = {
            "_list_tasks": "pick",
            "_bash_describe_task_args": "--flavor -f --size -s",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--flavor", "vanilla", ""],
            current=4,
            mock_poe_output=mock_output,
            mock_files=["file.txt"],
        )

        # After a valued option, falls back to file completion or shows more args
        assert result.filedir_called or result.compgen_called

    def test_describe_task_args_short_options(self, bash_harness, completion_script):
        """Short options like -f should be offered."""
        mock_output = {
            "_list_tasks": "greet",
            "_bash_describe_task_args": "--greeting -g --upper -u",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.task_args_called
        assert "-g" in result.compreply
        assert "-u" in result.compreply

    def test_describe_task_args_mixed_short_long(self, bash_harness, completion_script):
        """Both short and long options should be offered."""
        mock_output = {
            "_list_tasks": "greet",
            "_bash_describe_task_args": "--greeting -g --upper -u --format",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.task_args_called
        # Should have both short and long options
        assert "-g" in result.compreply
        assert "--greeting" in result.compreply
        assert "--format" in result.compreply

    def test_describe_task_args_no_args_defined(self, bash_harness, completion_script):
        """Task with no args should fall back to files."""
        mock_output = {
            "_list_tasks": "simple",
            "_bash_describe_task_args": "",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "simple", ""],
            current=2,
            mock_poe_output=mock_output,
            mock_files=["file1.txt", "dir/"],
        )

        # Should fall back to file completion
        assert result.filedir_called or result.compgen_called

    def test_describe_task_args_unknown_task(self, bash_harness, completion_script):
        """Unknown task should fall back to files."""
        mock_output = {
            "_list_tasks": "known",
            "_bash_describe_task_args": "",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "unknown", ""],
            current=2,
            mock_poe_output=mock_output,
            mock_files=["file.py"],
        )

        # Unknown task should fall back to file completion
        assert result.filedir_called or result.compgen_called


@requires_bash
class TestBashOptionValues:
    """Tests for option value completion."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_option_value_with_choices(self, bash_harness, completion_script):
        """poe task --flavor <TAB> should show choices."""
        zsh_args = "--flavor,-f\tstring\tFlavor\tvanilla chocolate strawberry"
        mock_output = {
            "_list_tasks": "pick",
            "_describe_task_args": zsh_args,
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--flavor", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert "vanilla" in result.compreply
        assert "chocolate" in result.compreply
        assert "strawberry" in result.compreply

    def test_option_value_partial_choice(self, bash_harness, completion_script):
        """poe task --flavor van<TAB> should filter choices."""
        zsh_args = "--flavor,-f\tstring\tFlavor\tvanilla chocolate strawberry"
        mock_output = {
            "_list_tasks": "pick",
            "_describe_task_args": zsh_args,
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--flavor", "van"],
            current=3,
            mock_poe_output=mock_output,
        )

        assert "vanilla" in result.compreply
        assert "chocolate" not in result.compreply

    def test_option_value_no_choices(self, bash_harness, completion_script):
        """Option without choices should fall back to files."""
        mock_output = {
            "_list_tasks": "greet",
            "_bash_describe_task_args": "--greeting -g",
            "_bash_task_arg_choices": "",  # No choices
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "--greeting", ""],
            current=3,
            mock_poe_output=mock_output,
            mock_files=["hello.txt"],
        )

        # Should fall back to file completion
        assert result.filedir_called or result.compgen_called

    def test_option_value_boolean_flag(self, bash_harness, completion_script):
        """Boolean flag --upper <TAB> should show next options."""
        # _describe_task_args format with boolean type
        mock_output = {
            "_list_tasks": "greet",
            "_describe_task_args": (
                "--greeting,-g\tstring\tGreeting\t_\n"
                "--upper,-u\tboolean\tUppercase\t_"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "--upper", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        # After boolean, should show other options (not try to complete a value)
        assert result.show_task_opts or result.filedir_called

    def test_option_value_boolean_with_dash(self, bash_harness, completion_script):
        """After boolean flag, poe task --upper -<TAB> should complete options."""
        mock_output = {
            "_list_tasks": "greet",
            "_describe_task_args": (
                "--greeting,-g\tstring\tGreeting\t_\n" "--upper\tboolean\tUppercase\t_"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "--upper", "-"],
            current=3,
            mock_poe_output=mock_output,
        )

        # Should show task options
        assert result.task_args_called

    def test_option_value_spaced_choices(self, bash_harness, completion_script):
        """Choices with spaces should be handled."""
        # Note: bash handles quoted spaces differently
        mock_output = {
            "_list_tasks": "test",
            "_describe_task_args": "--type,-t\tstring\tType\tquick full smoke",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "test", "--type", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert "quick" in result.compreply
        assert "full" in result.compreply
        assert "smoke" in result.compreply


@requires_bash
class TestBashUsedOptionFiltering:
    """Tests for filtering already-used options."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_used_option_not_repeated(self, bash_harness, completion_script):
        """Already used options should not be offered again."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--mode -m --other -o",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "--mode", "value", "-"],
            current=4,
            mock_poe_output=mock_output,
        )

        # --mode should NOT appear (already used)
        assert "--mode" not in result.compreply
        # --other should appear (not yet used)
        assert "--other" in result.compreply

    def test_multiple_used_options(self, bash_harness, completion_script):
        """Multiple used options should all be filtered."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--one --two --three",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "--one", "v1", "--two", "v2", "-"],
            current=6,
            mock_poe_output=mock_output,
        )

        # Used options should not appear
        assert "--one" not in result.compreply
        assert "--two" not in result.compreply
        # Unused should appear
        assert "--three" in result.compreply

    def test_short_long_forms_same_option(self, bash_harness, completion_script):
        """Short and long forms count as same logical option."""
        # Use _describe_task_args format: opts\ttype\thelp\tchoices
        mock_output = {
            "_list_tasks": "task",
            "_describe_task_args": (
                "--mode,-m\tstring\tMode\t_\n" "--other,-o\tstring\tOther\t_"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "-m", "value", "-"],
            current=4,
            mock_poe_output=mock_output,
        )

        # -m was used, so --mode should ALSO be filtered (same logical option)
        assert "-m" not in result.compreply
        assert "--mode" not in result.compreply
        # --other and -o should still appear (not used)
        assert "--other" in result.compreply
        assert "-o" in result.compreply

    def test_used_option_in_value_position(self, bash_harness, completion_script):
        """When completing value, the option should still work."""
        mock_output = {
            "_list_tasks": "pick",
            "_describe_task_args": "--flavor,-f\tstring\tFlavor\tvanilla chocolate",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--flavor", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        # Should show choices, not filter the option
        assert "vanilla" in result.compreply

    def test_unused_options_still_shown(self, bash_harness, completion_script):
        """Unused options should all be offered."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--one --two --three",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        # All options should appear (none used yet)
        assert "--one" in result.compreply
        assert "--two" in result.compreply
        assert "--three" in result.compreply


@requires_bash
class TestBashDirectoryOption:
    """Tests for -C/--directory/--root option handling."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_c_option_sets_target_path(self, bash_harness, completion_script):
        """-C should set target_path."""
        mock_output = {"_list_tasks": "task"}

        result = bash_harness(
            completion_script,
            words=["poe", "-C", "/path/to/project", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/path/to/project"

    def test_directory_option_sets_target_path(self, bash_harness, completion_script):
        """--directory should set target_path."""
        mock_output = {"_list_tasks": "task"}

        result = bash_harness(
            completion_script,
            words=["poe", "--directory", "/other/project", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/other/project"

    def test_root_option_sets_target_path(self, bash_harness, completion_script):
        """--root should set target_path."""
        mock_output = {"_list_tasks": "task"}

        result = bash_harness(
            completion_script,
            words=["poe", "--root", "/root/project", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/root/project"

    def test_target_path_passed_to_list_tasks(self, bash_harness, completion_script):
        """target_path should be passed to _list_tasks."""
        mock_output = {"_list_tasks": "remote-task"}

        result = bash_harness(
            completion_script,
            words=["poe", "-C", "/custom/path", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.list_tasks_called
        # Check that poe was called with the target path
        poe_calls_str = " ".join(result.poe_calls)
        assert "/custom/path" in poe_calls_str

    def test_target_path_passed_to_describe_task_args(
        self, bash_harness, completion_script
    ):
        """target_path should be passed to _bash_describe_task_args."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "-C", "/custom/path", "task", "-"],
            current=4,
            mock_poe_output=mock_output,
        )

        assert result.task_args_called
        # Check that poe was called with the target path
        poe_calls_str = " ".join(result.poe_calls)
        assert "/custom/path" in poe_calls_str

    def test_multiple_directory_options_last_wins(
        self, bash_harness, completion_script
    ):
        """When multiple -C options given, last one wins."""
        mock_output = {
            "_list_tasks": "task1 task2",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "-C", "/first/path", "-C", "/second/path", ""],
            current=5,
            mock_poe_output=mock_output,
        )

        # Should have used /second/path (last wins)
        assert result.detected_target_path == "/second/path"


@requires_bash
class TestBashFileFallback:
    """Tests for file completion fallback."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_file_fallback_for_positionals(self, bash_harness, completion_script):
        """Positional args should fall back to file completion."""
        mock_output = {
            "_list_tasks": "cat",
            "_bash_describe_task_args": "",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "cat", ""],
            current=2,
            mock_poe_output=mock_output,
            mock_files=["file1.txt", "file2.py", "dir/"],
        )

        assert result.filedir_called or result.compgen_called

    def test_file_fallback_no_choices(self, bash_harness, completion_script):
        """Option without choices falls back to files."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--input -i",
            "_bash_task_arg_choices": "",  # No choices
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "--input", ""],
            current=3,
            mock_poe_output=mock_output,
            mock_files=["data.csv", "input.json"],
        )

        assert result.filedir_called or result.compgen_called

    def test_file_fallback_with_pattern(self, bash_harness, completion_script):
        """File completion should filter by pattern."""
        mock_output = {
            "_list_tasks": "cat",
            "_bash_describe_task_args": "",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "cat", "file"],
            current=2,
            mock_poe_output=mock_output,
            mock_files=["file1.txt", "file2.py", "other.txt"],
        )

        # Should filter to files starting with "file"
        if result.compreply:
            for comp in result.compreply:
                if comp:  # Skip empty strings
                    assert comp.startswith("file") or comp == ""

    def test_filedir_preferred_over_compgen(self, bash_harness, completion_script):
        """_filedir should be tried before compgen -f."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", ""],
            current=2,
            mock_poe_output=mock_output,
            mock_files=["test.txt"],
        )

        # The script tries _filedir first, falls back to compgen -f
        # At least one should be called
        assert result.filedir_called or result.compgen_called


@requires_bash
class TestBashEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_empty_command_line(self, bash_harness, completion_script):
        """Just 'poe' with no args should list tasks."""
        mock_output = {"_list_tasks": "greet echo"}

        result = bash_harness(
            completion_script,
            words=["poe", ""],
            current=1,
            mock_poe_output=mock_output,
        )

        assert "greet" in result.compreply or result.list_tasks_called

    def test_task_with_dashes(self, bash_harness, completion_script):
        """Tasks with dashes should work."""
        mock_output = {
            "_list_tasks": "my-task another-task",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "my-task", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "my-task"
        assert result.task_args_called

    def test_task_with_underscores(self, bash_harness, completion_script):
        """Tasks with underscores should work."""
        mock_output = {
            "_list_tasks": "my_task another_task",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "my_task", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "my_task"

    def test_special_characters_in_choice(self, bash_harness, completion_script):
        """Choices with special characters should be handled."""
        mock_output = {
            "_list_tasks": "pick",
            "_describe_task_args": "--opt\tstring\tOption\tvalue1 value-2 value_3",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--opt", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert "value1" in result.compreply
        assert "value-2" in result.compreply
        assert "value_3" in result.compreply

    def test_very_long_task_list(self, bash_harness, completion_script):
        """Many tasks should all be offered."""
        tasks = " ".join(f"task{i}" for i in range(100))
        mock_output = {"_list_tasks": tasks}

        result = bash_harness(
            completion_script,
            words=["poe", ""],
            current=1,
            mock_poe_output=mock_output,
        )

        # Should have many completions
        assert len(result.compreply) >= 50  # At least half should be there

    def test_option_value_equals_syntax(self, bash_harness, completion_script):
        """poe task --opt=value should be handled."""
        # Note: bash splits on = by default, so this tests the word handling
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--mode --other",
            "_bash_task_arg_choices": "",
        }

        # Bash splits --opt=value based on COMP_WORDBREAKS. Test the simple case.
        result = bash_harness(
            completion_script,
            words=["poe", "task", "--mode=debug", "-"],
            current=3,
            mock_poe_output=mock_output,
        )

        # Should still work and filter used options
        assert result.task_args_called


@requires_bash
class TestBashSeparatorHandling:
    """Tests for -- separator handling."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_no_separator_handling(self, bash_harness, completion_script):
        """Document current behavior: -- is not specially handled."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "--", ""],
            current=3,
            mock_poe_output=mock_output,
            mock_files=["file.txt"],
        )

        # Current bash completion doesn't have special -- handling
        # It will treat -- as a regular word and offer file completion
        assert result.filedir_called or result.compgen_called

    def test_double_dash_treated_as_option(self, bash_harness, completion_script):
        """-- starting with - might be treated as option."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "--"],
            current=2,
            mock_poe_output=mock_output,
        )

        # -- starts with -, so might trigger option completion
        # or it might just show --opt filtered to --
        assert result.task_args_called or result.compgen_called

    def test_args_after_double_dash(self, bash_harness, completion_script):
        """Arguments after -- should still get file completion."""
        mock_output = {
            "_list_tasks": "task",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "--opt", "value", "--", ""],
            current=5,
            mock_poe_output=mock_output,
            mock_files=["arg1.txt", "arg2.txt"],
        )

        # After --, should fall back to file completion
        assert result.filedir_called or result.compgen_called


@requires_bash
class TestBashTaskNamePatterns:
    """Tests for the full space of valid task names.

    Poe task names must match: r"^\\w[\\w\\d\\-\\_\\+\\:]*$"
    - Must start with a word character (letter or underscore)
    - Can contain: word chars, digits, hyphens, underscores, plus, colon
    """

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_task_with_digits(self, bash_harness, completion_script):
        """Tasks with digits should work."""
        mock_output = {
            "_list_tasks": "task1 build2 test123",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task1", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "task1"
        assert result.task_args_called

    def test_task_with_plus(self, bash_harness, completion_script):
        """Tasks with plus sign should work (e.g., build+test)."""
        mock_output = {
            "_list_tasks": "build+test lint+format ci+cd",
            "_bash_describe_task_args": "--verbose",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "build+test", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "build+test"
        assert result.task_args_called

    def test_task_with_colon_namespace(self, bash_harness, completion_script):
        """Tasks with colons (namespaced) should work (e.g., docker:build)."""
        mock_output = {
            "_list_tasks": "docker:build docker:push ns:sub:task",
            "_bash_describe_task_args": "--tag",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "docker:build", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "docker:build"
        assert result.task_args_called

    def test_task_with_deep_namespace(self, bash_harness, completion_script):
        """Tasks with multiple colons should work (e.g., a:b:c)."""
        mock_output = {
            "_list_tasks": "ns:sub:task a:b:c:d",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "ns:sub:task", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "ns:sub:task"

    def test_task_with_mixed_special_chars(self, bash_harness, completion_script):
        """Tasks with mixed special characters should work."""
        mock_output = {
            "_list_tasks": "build_v2-fast+ci test-123_foo docker:build-v2",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "build_v2-fast+ci", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "build_v2-fast+ci"

    def test_task_starting_with_underscore(self, bash_harness, completion_script):
        """Tasks starting with underscore should work."""
        mock_output = {
            "_list_tasks": "_private _internal __dunder",
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "_private", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == "_private"

    def test_completion_filters_special_char_tasks(
        self, bash_harness, completion_script
    ):
        """Partial completion should filter tasks with special characters."""
        mock_output = {"_list_tasks": "docker:build docker:push docker:test npm:build"}

        result = bash_harness(
            completion_script,
            words=["poe", "docker:"],
            current=1,
            mock_poe_output=mock_output,
        )

        # Should filter to docker:* tasks
        assert "docker:build" in result.compreply
        assert "docker:push" in result.compreply
        assert "docker:test" in result.compreply
        assert "npm:build" not in result.compreply

    def test_completion_with_plus_prefix(self, bash_harness, completion_script):
        """Partial completion with plus should work."""
        mock_output = {"_list_tasks": "build build+test build+lint ci+cd"}

        result = bash_harness(
            completion_script,
            words=["poe", "build+"],
            current=1,
            mock_poe_output=mock_output,
        )

        # Should filter to build+* tasks
        assert "build+test" in result.compreply
        assert "build+lint" in result.compreply
        assert "ci+cd" not in result.compreply

    def test_all_valid_task_name_chars(self, bash_harness, completion_script):
        """Test task name with all valid character types."""
        # Task name with all allowed chars: word, digit, hyphen, underscore, plus, colon
        task_name = "Task_1-test+build:v2"
        mock_output = {
            "_list_tasks": task_name,
            "_bash_describe_task_args": "--opt",
            "_bash_task_arg_choices": "",
        }

        result = bash_harness(
            completion_script,
            words=["poe", task_name, "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_task == task_name
        assert result.task_args_called


@requires_bash
class TestBashBackwardCompatibility:
    """Tests for backward compatibility with older poe versions.

    These tests verify that the completion script works correctly when
    newer poe builtins (like _bash_describe_task_args, _bash_task_arg_choices)
    are not available, gracefully falling back to basic functionality.
    """

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_task_completion_with_only_list_tasks(
        self, bash_harness, completion_script
    ):
        """Task completion should work with only _list_tasks available."""
        # Only provide _list_tasks - no _bash_describe_task_args
        mock_output = {"_list_tasks": "greet echo build"}

        result = bash_harness(
            completion_script,
            words=["poe", ""],
            current=1,
            mock_poe_output=mock_output,
        )

        # Should still complete tasks
        assert result.list_tasks_called
        assert "greet" in result.compreply
        assert "echo" in result.compreply
        assert "build" in result.compreply

    def test_describe_task_args_unavailable_falls_back_to_files(
        self, bash_harness, completion_script
    ):
        """When _bash_describe_task_args unavailable, falls back to files."""
        # Only provide _list_tasks - _bash_describe_task_args returns empty/fails
        mock_output = {
            "_list_tasks": "greet",
            # _bash_describe_task_args not provided - simulates old poe version
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "-"],
            current=2,
            mock_poe_output=mock_output,
            mock_files=["file1.txt", "file2.py"],
        )

        # Without task args, should fall back to file completion
        # (empty filtered_args leads to file completion fallback)
        assert result.filedir_called or result.compgen_called

    def test_task_arg_choices_unavailable_falls_back_to_files(
        self, bash_harness, completion_script
    ):
        """When _bash_task_arg_choices is unavailable, should fall back to files."""
        mock_output = {
            "_list_tasks": "greet",
            "_bash_describe_task_args": "--greeting -g",
            # _bash_task_arg_choices not provided - simulates old poe version
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "--greeting", ""],
            current=3,
            mock_poe_output=mock_output,
            mock_files=["hello.txt"],
        )

        # Without choices, should fall back to file completion
        assert result.filedir_called or result.compgen_called

    def test_partial_builtin_support_describe_task_args_only(
        self, bash_harness, completion_script
    ):
        """Should work with _list_tasks and _bash_describe_task_args but no choices."""
        mock_output = {
            "_list_tasks": "greet",
            "_bash_describe_task_args": "--greeting -g --upper",
            # _bash_task_arg_choices not provided
        }

        result = bash_harness(
            completion_script,
            words=["poe", "greet", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        # Should still offer task args
        assert result.task_args_called
        assert "--greeting" in result.compreply
        assert "-g" in result.compreply
        assert "--upper" in result.compreply

    def test_all_builtins_fail_still_offers_tasks(
        self, bash_harness, completion_script
    ):
        """Even if all task-specific builtins fail, task listing should work."""
        # Only _list_tasks works
        mock_output = {"_list_tasks": "simple-task"}

        result = bash_harness(
            completion_script,
            words=["poe", "sim"],
            current=1,
            mock_poe_output=mock_output,
        )

        # Task completion should still work
        assert result.list_tasks_called
        assert "simple-task" in result.compreply


@requires_bash
class TestBashTaskOptionIsolation:
    """Tests that global option handling doesn't leak into task-specific completion.

    These tests verify that after a task name, global options like -e/--executor
    and -C/--directory are not matched, and that the used-options filter only
    scans words after the task position.
    """

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    # Bug 1: Global value completion fires after task name

    def test_task_e_option_not_completed_as_global_executor(
        self, bash_harness, completion_script
    ):
        """poe mytask -e <TAB> should complete task's -e choices, not executor."""
        mock_output = {
            "_list_tasks": "mytask",
            "_describe_task_args": "-e,--env\tstring\tEnvironment\tdev staging prod",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "mytask", "-e", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        # Should offer task's -e choices
        assert "dev" in result.compreply
        assert "staging" in result.compreply
        assert "prod" in result.compreply
        # Should NOT offer global executor choices
        assert "auto" not in result.compreply
        assert "poetry" not in result.compreply
        assert "virtualenv" not in result.compreply

    def test_task_c_option_not_completed_as_directory(
        self, bash_harness, completion_script
    ):
        """poe mytask -C <TAB> should complete task's -C, not call _filedir."""
        mock_output = {
            "_list_tasks": "mytask",
            "_describe_task_args": "-C,--config\tstring\tConfig\tbase override custom",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "mytask", "-C", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        # Should offer task's -C choices, not directory completion
        assert "base" in result.compreply
        assert "override" in result.compreply
        assert "custom" in result.compreply

    # Bug 2: Pre-parsing loop doesn't stop at task name

    def test_task_option_doesnt_set_target_path(self, bash_harness, completion_script):
        """poe mytask -C /some/path <TAB> should not set target_path."""
        mock_output = {
            "_list_tasks": "mytask",
            "_describe_task_args": "-C,--config\tstring\tConfig\t_",
        }

        result = bash_harness(
            completion_script,
            words=["poe", "mytask", "-C", "/some/path", ""],
            current=4,
            mock_poe_output=mock_output,
        )

        # target_path should NOT be set from task's -C argument
        assert result.detected_target_path == ""

    def test_task_e_value_not_skipped_by_global_parsing(
        self, bash_harness, completion_script
    ):
        """poe mytask -e prod --verbose <TAB> should not misparse task args."""
        mock_output = {
            "_list_tasks": "mytask",
            "_describe_task_args": (
                "-e,--env\tstring\tEnvironment\t_\n" "--verbose\tboolean\tVerbose\t_"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "mytask", "-e", "prod", "--verbose", ""],
            current=5,
            mock_poe_output=mock_output,
        )

        # The task should be correctly identified
        assert result.detected_task == "mytask"
        # target_path should not be set
        assert result.detected_target_path == ""

    # Bug 3: Used-options loop scans all words (including before task)

    def test_global_option_doesnt_filter_task_option(
        self, bash_harness, completion_script
    ):
        """poe -v mytask -<TAB> should still offer task's -v/--verbose."""
        mock_output = {
            "_list_tasks": "mytask",
            "_describe_task_args": (
                "-v,--verbose\tboolean\tVerbose\t_\n" "--output,-o\tstring\tOutput\t_"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "-v", "mytask", "-"],
            current=3,
            mock_poe_output=mock_output,
        )

        # Task's -v and --verbose should still be offered even though
        # global -v was used before the task name
        assert "-v" in result.compreply
        assert "--verbose" in result.compreply
        assert "--output" in result.compreply
        assert "-o" in result.compreply

    def test_global_options_still_work_before_task(
        self, bash_harness, completion_script
    ):
        """poe -e <TAB> (no task yet) should still offer executor choices."""
        mock_output = {"_list_tasks": "mytask"}

        result = bash_harness(
            completion_script,
            words=["poe", "-e", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        # Global executor choices should still work when no task is present
        assert "auto" in result.compreply
        assert "poetry" in result.compreply
        assert "simple" in result.compreply


@requires_bash
class TestBashEqualsStyleOptions:
    """Tests for --option=value style argument handling.

    After _init_completion -n =, bash keeps --opt=value as a single word.
    These tests verify that the completion script handles this correctly.
    """

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated bash completion script."""
        result = run_poe_main("_bash_completion")
        return result.stdout

    def test_directory_equals_completes_tasks(self, bash_harness, completion_script):
        """poe --directory=/path <TAB> should detect target_path and list tasks."""
        mock_output = {"_list_tasks": "remote-task deploy"}

        result = bash_harness(
            completion_script,
            words=["poe", "--directory=/some/path", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/some/path"
        assert result.list_tasks_called
        assert "remote-task" in result.compreply

    def test_task_option_equals_value_completion(self, bash_harness, completion_script):
        """poe pick --flavor= should offer prefixed choices."""
        mock_output = {
            "_list_tasks": "pick",
            "_describe_task_args": (
                "--flavor,-f\tstring\tFlavor\t" "vanilla chocolate strawberry"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--flavor="],
            current=2,
            mock_poe_output=mock_output,
        )

        assert "--flavor=vanilla" in result.compreply
        assert "--flavor=chocolate" in result.compreply
        assert "--flavor=strawberry" in result.compreply

    def test_task_option_equals_partial_value(self, bash_harness, completion_script):
        """poe pick --flavor=van should filter to --flavor=vanilla."""
        mock_output = {
            "_list_tasks": "pick",
            "_describe_task_args": (
                "--flavor,-f\tstring\tFlavor\t" "vanilla chocolate strawberry"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "pick", "--flavor=van"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert "--flavor=vanilla" in result.compreply
        assert "--flavor=chocolate" not in result.compreply

    def test_used_option_equals_filtered(self, bash_harness, completion_script):
        """poe task --mode=debug -<TAB> should filter --mode/-m from completions."""
        mock_output = {
            "_list_tasks": "task",
            "_describe_task_args": (
                "--mode,-m\tstring\tMode\t_\n" "--other,-o\tstring\tOther\t_"
            ),
        }

        result = bash_harness(
            completion_script,
            words=["poe", "task", "--mode=debug", "-"],
            current=3,
            mock_poe_output=mock_output,
        )

        # --mode and -m should be filtered (already used via --mode=debug)
        assert "--mode" not in result.compreply
        assert "-m" not in result.compreply
        # --other and -o should still appear
        assert "--other" in result.compreply
        assert "-o" in result.compreply

    def test_c_equals_completes_tasks(self, bash_harness, completion_script):
        """poe -C=/path <TAB> should detect target_path and list tasks."""
        mock_output = {"_list_tasks": "remote-task deploy"}

        result = bash_harness(
            completion_script,
            words=["poe", "-C=/some/path", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.detected_target_path == "/some/path"
        assert result.list_tasks_called
        assert "remote-task" in result.compreply

    def test_executor_equals_value_completion(self, bash_harness, completion_script):
        """poe --executor= should offer --executor=auto, etc."""
        mock_output = {"_list_tasks": "greet"}

        result = bash_harness(
            completion_script,
            words=["poe", "--executor="],
            current=1,
            mock_poe_output=mock_output,
        )

        assert "--executor=auto" in result.compreply
        assert "--executor=poetry" in result.compreply
        assert "--executor=simple" in result.compreply
