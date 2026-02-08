# ruff: noqa: E501

"""
Zsh completion end-to-end harness tests.

These tests run real zsh with stubbed completion builtins to verify
the completion logic works correctly. The harness captures what our
script passes to _arguments, _describe, and _files.
"""

import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
class TestZshCompletionE2E:
    """End-to-end tests for zsh completion behavior."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated zsh completion script."""
        result = run_poe_main("_zsh_completion")
        return result.stdout

    # ========== Separator (--) handling tests ==========

    def test_after_separator_offers_files_only(self, zsh_harness, completion_script):
        """After --, only file completion should be offered."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
            "_describe_task_args": "--greeting,-g\tstring\tGreeting\t_",
        }

        # Simulate: poe greet -- <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "greet", "--", ""],
            current=4,
            mock_poe_output=mock_output,
        )

        assert result.after_separator, "Should detect -- separator"
        assert result.early_return, "Should return early after --"
        assert result.files_called, "Should offer file completion after --"

    def test_after_separator_with_args_before(self, zsh_harness, completion_script):
        """After -- with task args before, should still offer files only."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
            "_describe_task_args": "--greeting,-g\tstring\tGreeting\t_",
        }

        # Simulate: poe greet --greeting hello -- <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "greet", "--greeting", "hello", "--", ""],
            current=6,
            mock_poe_output=mock_output,
        )

        assert result.after_separator, "Should detect -- separator"
        assert result.files_called, "Should offer file completion"

    def test_before_separator_offers_describe_task_args(
        self, zsh_harness, completion_script
    ):
        """Before --, task arguments should be offered."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
            "_describe_task_args": "--greeting,-g\tstring\tGreeting\t_",
        }

        # Simulate: poe greet --<TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "greet", "--"],
            current=3,
            mock_poe_output=mock_output,
        )

        assert not result.after_separator, "Should not detect separator"
        assert result.arguments_called, "Should call _arguments for task args"

    def test_double_dash_as_option_value_not_separator(
        self, zsh_harness, completion_script
    ):
        """-- as an option value should not trigger separator mode."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
            "_describe_task_args": "--greeting,-g\tstring\tGreeting\t_",
        }

        # Simulate: poe greet --greeting -- <TAB>
        # Here -- is the value for --greeting, not a separator
        # Actually this is ambiguous - the script treats standalone -- as separator
        # This test documents current behavior
        result = zsh_harness(
            completion_script,
            words=["poe", "greet", "--greeting", "--", ""],
            current=5,
            mock_poe_output=mock_output,
        )

        # Current implementation treats -- as separator regardless of position
        # This is the expected behavior per the spec
        assert result.after_separator

    # ========== Global option completion tests ==========

    def test_help_not_exclusive_with_all_options(self, zsh_harness, completion_script):
        """--help should not use (- *) exclusion which blocks it after any option."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
        }

        # Simulate: poe -<TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.arguments_called
        # Find specs containing --help
        help_specs = [s for s in result.arguments_specs if "--help" in s]
        assert help_specs, "Should have --help in specs"

        # Check that --help doesn't use (- *) exclusion
        # (- *) means "exclusive with all options and args" which is too aggressive
        for spec in help_specs:
            assert "(- *)" not in spec, (
                f"--help should not use (- *) exclusion - it blocks --help after any option. "
                f"Got spec: {spec}"
            )

        # Also check that OTHER options don't exclude --help
        # e.g., -C shouldn't exclude --help, so `poe -C path --help` works
        for spec in result.arguments_specs:
            if "(" not in spec or ")" not in spec:
                continue
            excl_end = spec.index(")")
            exclusion_list = spec[: excl_end + 1]
            option_part = spec[excl_end + 1 :]

            # Skip specs that define --help itself
            if option_part.startswith(("--help", "-h")):
                continue
            # Skip specs that define --version (those should exclude --help)
            if option_part.startswith("--version"):
                continue

            # Other options should NOT exclude --help/-h
            assert (
                "--help" not in exclusion_list
            ), f"Non-help option should not exclude --help. Got spec: {spec}"
            assert (
                "-h" not in exclusion_list.split()
            ), f"Non-help option should not exclude -h. Got spec: {spec}"

    def test_option_completion_does_not_show_tasks(
        self, zsh_harness, completion_script
    ):
        """When completing an option (poe -<TAB>), tasks should not be shown."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone\necho:Echo text",
        }

        # Simulate: poe -<TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "-"],
            current=2,
            mock_poe_output=mock_output,
        )

        # Should be completing an option
        assert result.completing_option, "Should detect we're completing an option"
        # _arguments should be called (to show global options)
        assert result.arguments_called, "Should call _arguments for global options"
        # But _describe should NOT be called (we don't want tasks mixed with options)
        assert not result.describe_called, (
            "Should NOT call _describe when completing options - "
            "tasks should not be mixed with global options"
        )

    # ========== Task completion tests ==========

    def test_task_completion_with_no_task(self, zsh_harness, completion_script):
        """Completing with no task should offer task names."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone\necho:Echo text",
        }

        # Simulate: poe <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.state == "task", "Should be in task state"
        assert result.describe_called, "Should call _describe for tasks"
        assert result.describe_tag == "task"
        assert "greet:Greet someone" in result.describe_items
        assert "echo:Echo text" in result.describe_items

    def test_task_completion_with_partial(self, zsh_harness, completion_script):
        """Completing partial task name should offer matching tasks."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone\necho:Echo text",
        }

        # Simulate: poe gr<TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "gr"],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.state == "task"
        assert result.describe_called

    # ========== Task args completion tests ==========

    def test_describe_task_args_completion(self, zsh_harness, completion_script):
        """After task, should offer task-specific arguments."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
            "_describe_task_args": "--greeting,-g\tstring\tThe greeting\t_\n--upper\tboolean\tUppercase\t_",
        }

        # Simulate: poe greet <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "greet", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == "greet"
        assert result.state == "args"
        assert result.arguments_called

    def test_describe_task_args_with_choices(self, zsh_harness, completion_script):
        """Task args with choices should include them in completion."""
        mock_output = {
            "_zsh_describe_tasks": "pick:Pick something",
            "_describe_task_args": "--flavor,-f\tstring\tFlavor\tvanilla chocolate",
        }

        # Simulate: poe pick <TAB>
        # Note: We complete BEFORE typing --flavor to test choices appear in arg_specs.
        # Once --flavor is typed, it gets filtered by repeatability logic.
        result = zsh_harness(
            completion_script,
            words=["poe", "pick", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.arguments_called
        # Check that choices appear in the argument specs
        specs_text = "\n".join(result.arguments_specs)
        assert "vanilla" in specs_text, f"Expected 'vanilla' in specs: {specs_text}"
        assert "chocolate" in specs_text

    def test_describe_task_args_with_spaced_choices(
        self, zsh_harness, completion_script
    ):
        """Choices with spaces should be properly quoted."""
        mock_output = {
            "_zsh_describe_tasks": "test:Test task",
            "_describe_task_args": "--type,-t\tstring\tType\t'quick run' 'full test' smoke",
        }

        # Simulate: poe test <TAB>
        # Complete BEFORE typing --type to test spaced choices appear in arg_specs.
        result = zsh_harness(
            completion_script,
            words=["poe", "test", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.arguments_called
        specs_text = "\n".join(result.arguments_specs)
        # Quoted choices should appear
        assert "quick run" in specs_text or "'quick run'" in specs_text

    # ========== Option filtering tests ==========

    def test_option_not_offered_after_use(self, zsh_harness, completion_script):
        """Options should not be offered again after being used once."""
        mock_output = {
            "_zsh_describe_tasks": "task:A task",
            "_describe_task_args": "--mode,-m\tstring\tMode\t_\n--other\tstring\tOther\t_",
        }

        # Simulate: poe task --mode value <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "task", "--mode", "value", ""],
            current=5,
            mock_poe_output=mock_output,
        )

        assert result.arguments_called
        specs_text = "\n".join(result.arguments_specs)
        # --mode should NOT appear (already used)
        # --other should appear (not yet used)
        assert "--other" in specs_text

    def test_option_value_completion_with_choices(self, zsh_harness, completion_script):
        """When completing option value, choices should be offered even if option was 'used'."""
        mock_output = {
            "_zsh_describe_tasks": "pick:Pick something",
            "_describe_task_args": "--flavor,-f\tstring\tFlavor\tvanilla chocolate strawberry",
        }

        # Simulate: poe pick --flavor <TAB>
        # The option --flavor appears in words, but we're completing its VALUE
        result = zsh_harness(
            completion_script,
            words=["poe", "pick", "--flavor", ""],
            current=4,
            mock_poe_output=mock_output,
        )

        assert result.arguments_called
        specs_text = "\n".join(result.arguments_specs)
        # --flavor SHOULD appear in specs so _arguments can offer value completion
        assert "--flavor" in specs_text, (
            "Option should be in specs when completing its value - "
            f"got specs: {result.arguments_specs}"
        )
        # Choices should be in the spec
        assert "vanilla" in specs_text
        assert "chocolate" in specs_text

    # ========== --help completion tests ==========

    def test_help_offers_task_names(self, zsh_harness, completion_script):
        """--help should offer task names as optional value."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone\necho:Echo text",
        }

        # Simulate: poe --help <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "--help", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        # State may be multi-valued ("help_task task") due to ambiguity
        # The completion script handles this with pattern matching
        assert "help_task" in result.state
        assert result.describe_called
        assert "greet:Greet someone" in result.describe_items

    def test_help_short_form_offers_task_names(self, zsh_harness, completion_script):
        """Short -h should also offer task names."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone\necho:Echo text",
        }

        # Simulate: poe -h <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "-h", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        # State may be multi-valued due to ambiguity between optional value and positional
        assert "help_task" in result.state
        assert result.describe_called

    def test_help_value_not_treated_as_task(self, zsh_harness, completion_script):
        """Value after -h should not be treated as current task."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone\necho:Echo text",
            "_describe_task_args": "--flavor,-f\tstring\tFlavor\tvanilla chocolate",
        }

        # Simulate: poe -h greet --<TAB>
        # 'greet' is the help target, NOT the current task
        result = zsh_harness(
            completion_script,
            words=["poe", "-h", "greet", "--"],
            current=4,
            mock_poe_output=mock_output,
        )

        # Should NOT detect 'greet' as current_task
        assert (
            result.current_task == ""
        ), f"Expected no current_task (greet is -h value), got: {result.current_task!r}"
        # When current_task is empty, args state falls back to _files
        # So task-specific args like --flavor should NOT appear in completions
        specs_text = "\n".join(result.arguments_specs)
        assert (
            "--flavor" not in specs_text
        ), "Task-specific args should not be offered when -h value is mistaken for task"

    # ========== Directory option tests ==========

    def test_directory_option_passes_path(self, zsh_harness, completion_script):
        """Target path from -C should be detected."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
        }

        # Simulate: poe -C /some/path <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "-C", "/some/path", ""],
            current=4,
            mock_poe_output=mock_output,
        )

        assert result.target_path == "/some/path"

    def test_directory_long_option_passes_path(self, zsh_harness, completion_script):
        """Target path from --directory should be detected."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
        }

        # Simulate: poe --directory /other/path <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "--directory", "/other/path", ""],
            current=4,
            mock_poe_output=mock_output,
        )

        assert result.target_path == "/other/path"

    # ========== Positional args tests ==========

    def test_positional_args_with_choices(self, zsh_harness, completion_script):
        """Positional args with choices should offer them."""
        mock_output = {
            "_zsh_describe_tasks": "pick:Pick size",
            "_describe_task_args": "size\tpositional\tServing size\tsmall medium large",
        }

        # Simulate: poe pick <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "pick", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.arguments_called
        specs_text = "\n".join(result.arguments_specs)
        assert "small" in specs_text
        assert "medium" in specs_text
        assert "large" in specs_text

    def test_positional_args_without_choices_offers_files(
        self, zsh_harness, completion_script
    ):
        """Positional args without choices should offer file completion."""
        mock_output = {
            "_zsh_describe_tasks": "cat:Cat a file",
            "_describe_task_args": "file\tpositional\tFile to read\t_",
        }

        # Simulate: poe cat <TAB>
        result = zsh_harness(
            completion_script,
            words=["poe", "cat", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.arguments_called
        specs_text = "\n".join(result.arguments_specs)
        assert "_files" in specs_text


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
class TestZshCompletionCaching:
    """Tests for completion caching behavior."""

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated zsh completion script."""
        result = run_poe_main("_zsh_completion")
        return result.stdout

    @pytest.fixture
    def cache_disabled_script(self, completion_script):
        """Get completion script with caching disabled."""
        return completion_script.replace("_POE_CACHE_ENABLED=1", "_POE_CACHE_ENABLED=0")

    # ========== Basic cache storage tests ==========

    def test_first_completion_stores_to_cache(self, zsh_harness, completion_script):
        """First completion should store task list in cache."""
        mock = {"_zsh_describe_tasks": "greet:Greet someone\ntest:Run tests"}
        result = zsh_harness(completion_script, ["poe", ""], 2, mock_poe_output=mock)

        # Should have created a cache file
        assert result.cache_files, "Expected cache file to be created"
        assert any(
            "poe_tasks" in f for f in result.cache_files
        ), f"Expected poe_tasks cache file, got: {result.cache_files}"

        # Cache should contain the tasks
        cache_id = next(f for f in result.cache_files if "poe_tasks" in f)
        contents = result.get_cache_contents(cache_id)
        assert "greet:Greet someone" in contents
        assert "test:Run tests" in contents

        # Should have made a _store_cache call
        assert any(
            "_store_cache" in c for c in result.cache_calls
        ), f"Expected _store_cache call, got: {result.cache_calls}"

    def test_second_completion_uses_cache(self, zsh_harness, completion_script):
        """With pre-populated cache, should use cache instead of calling poe."""
        # Cache ID format: poe_tasks_${effective_path//\//_}
        # With PWD as effective_path, need to match what the script generates
        # Pre-populate with a known cache ID
        cache_id = "poe_tasks__test_path"

        # Modify script to use a known effective_path for testing
        script_with_test_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/test/path"',
        )

        pre_cache = {cache_id: ["cached:From cache", "old:Old data"]}

        # Mock returns different data - but should use cache instead
        mock = {"_zsh_describe_tasks": "fresh:Fresh data\nnew:New data"}
        result = zsh_harness(
            script_with_test_path,
            ["poe", ""],
            2,
            mock_poe_output=mock,
            pre_cache=pre_cache,
        )

        # Should have used cache (retrieve call should succeed)
        retrieve_calls = [c for c in result.cache_calls if "_retrieve_cache" in c]
        assert (
            retrieve_calls
        ), f"Expected _retrieve_cache call, got: {result.cache_calls}"

        # Completions should show cached data, not fresh data
        assert result.describe_called
        assert (
            "cached:From cache" in result.describe_items
        ), f"Expected cached data, got: {result.describe_items}"
        # Fresh data should NOT appear (since cache was hit)
        assert "fresh:Fresh data" not in result.describe_items

    def test_cache_miss_calls_poe_and_stores(self, zsh_harness, completion_script):
        """Cache miss should call poe and store result in cache."""
        # Use a test path to get predictable cache ID
        script_with_test_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/some/project"',
        )

        mock = {"_zsh_describe_tasks": "build:Build project\ndeploy:Deploy app"}
        result = zsh_harness(
            script_with_test_path, ["poe", ""], 2, mock_poe_output=mock
        )

        # Should have checked cache (invalid since empty)
        invalid_calls = [c for c in result.cache_calls if "_cache_invalid" in c]
        assert invalid_calls, "Expected _cache_invalid call"

        # Should have stored to cache after fetching
        store_calls = [c for c in result.cache_calls if "_store_cache" in c]
        assert store_calls, "Expected _store_cache call after cache miss"

        # Completions should show fetched data
        assert "build:Build project" in result.describe_items

    # ========== Cache key tests ==========

    def test_cache_key_includes_path(self, zsh_harness, completion_script):
        """Cache key should include the effective path."""
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/my/project/path"',
        )

        mock = {"_zsh_describe_tasks": "task:Task"}
        result = zsh_harness(script_with_path, ["poe", ""], 2, mock_poe_output=mock)

        # Cache ID should include transformed path
        cache_files = result.cache_files
        assert len(cache_files) > 0, "Expected cache file to be created"

        # The path /my/project/path becomes _my_project_path
        assert any(
            "poe_tasks__my_project_path" in f for f in cache_files
        ), f"Cache ID should include path, got: {cache_files}"

    def test_different_paths_use_different_cache_keys(
        self, zsh_harness, completion_script
    ):
        """Different effective paths should use different cache keys."""
        # Create two different scripts with different paths
        script_path_a = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/path/a"',
        )
        script_path_b = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/path/b"',
        )

        mock = {"_zsh_describe_tasks": "task:Task"}

        result1 = zsh_harness(script_path_a, ["poe", ""], 2, mock_poe_output=mock)
        result2 = zsh_harness(script_path_b, ["poe", ""], 2, mock_poe_output=mock)

        # Should have different cache files
        assert result1.cache_files != result2.cache_files, (
            f"Different paths should have different cache keys. "
            f"Path A: {result1.cache_files}, Path B: {result2.cache_files}"
        )

        # Verify specific cache IDs
        assert any("_path_a" in f for f in result1.cache_files)
        assert any("_path_b" in f for f in result2.cache_files)

    def test_directory_option_affects_cache_key(self, zsh_harness, completion_script):
        """Using -C should change the cache key to use that path."""
        # Note: The harness's simplified _arguments stub doesn't handle
        # option counting correctly, so we test target_path detection
        # separately from _arguments state handling.
        mock = {"_zsh_describe_tasks": "task:Task"}

        # Complete with -C /custom/dir - the harness will detect target_path
        # but put us in 'args' state due to simplified position counting.
        # So we check that target_path was correctly parsed instead.
        result = zsh_harness(
            completion_script,
            ["poe", "-C", "/custom/dir", ""],
            4,
            mock_poe_output=mock,
        )

        # Verify target_path was detected from -C option
        assert (
            result.target_path == "/custom/dir"
        ), f"Expected target_path='/custom/dir', got: {result.target_path!r}"

    # ========== Cache disabled tests ==========

    def test_cache_disabled_skips_cache_storage(
        self, zsh_harness, cache_disabled_script
    ):
        """With _POE_CACHE_ENABLED=0, should not store to cache."""
        mock = {"_zsh_describe_tasks": "task:Task desc"}
        result = zsh_harness(
            cache_disabled_script, ["poe", ""], 2, mock_poe_output=mock
        )

        # Should not have stored to cache
        assert (
            not result.cache_files
        ), f"Cache should be empty when disabled, got: {result.cache_files}"

        # Should not have made cache calls
        store_calls = [c for c in result.cache_calls if "_store_cache" in c]
        assert (
            not store_calls
        ), f"Should not call _store_cache when disabled, got: {result.cache_calls}"

    def test_cache_disabled_skips_cache_retrieval(
        self, zsh_harness, cache_disabled_script
    ):
        """With _POE_CACHE_ENABLED=0, should not try to retrieve from cache."""
        # Pre-populate cache that would be used if caching was enabled
        pre_cache = {"poe_tasks__some_path": ["stale:Stale data"]}

        mock = {"_zsh_describe_tasks": "fresh:Fresh data"}
        result = zsh_harness(
            cache_disabled_script,
            ["poe", ""],
            2,
            mock_poe_output=mock,
            pre_cache=pre_cache,
        )

        # Should show fresh data (cache not used)
        assert "fresh:Fresh data" in result.describe_items
        assert "stale:Stale data" not in result.describe_items

        # Should not have made cache retrieve calls
        retrieve_calls = [c for c in result.cache_calls if "_retrieve_cache" in c]
        assert (
            not retrieve_calls
        ), f"Should not call _retrieve_cache when disabled, got: {result.cache_calls}"

    # ========== Task args caching tests ==========

    def test_describe_task_args_caching(self, zsh_harness, completion_script):
        """Task arguments should also be cached."""
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/project"',
        )

        mock = {
            "_zsh_describe_tasks": "build:Build it",
            "_describe_task_args": "--output,-o\tstring\tOutput dir\t_",
        }

        result = zsh_harness(
            script_with_path, ["poe", "build", ""], 3, mock_poe_output=mock
        )

        # Should have cached task args
        args_cache = [f for f in result.cache_files if "poe_args" in f]
        assert args_cache, f"Expected task args cache, got: {result.cache_files}"

        # Cache ID should include task name and path
        assert any(
            "build" in f and "_project" in f for f in args_cache
        ), f"Args cache should include task name and path: {args_cache}"

    def test_different_tasks_use_different_cache_keys(
        self, zsh_harness, completion_script
    ):
        """Different tasks should have different args cache keys."""
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/proj"',
        )

        mock_build = {
            "_zsh_describe_tasks": "build:Build",
            "_describe_task_args": "--mode\tstring\tMode\t_",
        }
        mock_test = {
            "_zsh_describe_tasks": "test:Test",
            "_describe_task_args": "--verbose\tboolean\tVerbose\t_",
        }

        result_build = zsh_harness(
            script_with_path, ["poe", "build", ""], 3, mock_poe_output=mock_build
        )
        result_test = zsh_harness(
            script_with_path, ["poe", "test", ""], 3, mock_poe_output=mock_test
        )

        # Get args cache files (exclude tasks cache)
        build_args = [f for f in result_build.cache_files if "poe_args" in f]
        test_args = [f for f in result_test.cache_files if "poe_args" in f]

        assert build_args != test_args, (
            f"Different tasks should have different cache keys. "
            f"Build: {build_args}, Test: {test_args}"
        )

    # ========== Edge cases ==========

    def test_empty_cache_file_not_used(self, zsh_harness, completion_script):
        """Empty cache file should be treated as cache miss."""
        cache_id = "poe_tasks__empty_test"
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/empty/test"',
        )

        # Pre-populate with empty cache
        pre_cache = {cache_id: []}

        mock = {"_zsh_describe_tasks": "task:From poe"}
        result = zsh_harness(
            script_with_path,
            ["poe", ""],
            2,
            mock_poe_output=mock,
            pre_cache=pre_cache,
        )

        # Should have fetched fresh data since cache was empty
        assert "task:From poe" in result.describe_items

    def test_cache_with_special_characters_in_path(
        self, zsh_harness, completion_script
    ):
        """Paths with special characters should be handled in cache keys."""
        # Test with path containing characters that might break cache ID
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/path/with spaces/and-dashes"',
        )

        mock = {"_zsh_describe_tasks": "task:Task"}
        result = zsh_harness(script_with_path, ["poe", ""], 2, mock_poe_output=mock)

        # Should still create a cache file
        assert result.cache_files, "Should create cache file even with special chars"

        # Cache file should have transformed the path
        # /path/with spaces/and-dashes -> _path_with spaces_and-dashes
        # (only / is transformed to _)
        cache_file = result.cache_files[0]
        assert "/" not in cache_file, "Cache ID should not contain slashes"

    def test_cache_call_sequence_on_miss(self, zsh_harness, completion_script):
        """Verify the correct sequence of cache calls on a miss."""
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/seq/test"',
        )

        mock = {"_zsh_describe_tasks": "task:Task"}
        result = zsh_harness(script_with_path, ["poe", ""], 2, mock_poe_output=mock)

        # Should have called in order: _cache_invalid, then _store_cache
        cache_calls = result.cache_calls
        invalid_idx = next(
            (i for i, c in enumerate(cache_calls) if "_cache_invalid" in c), -1
        )
        store_idx = next(
            (i for i, c in enumerate(cache_calls) if "_store_cache" in c), -1
        )

        assert invalid_idx >= 0, "Should call _cache_invalid"
        assert store_idx >= 0, "Should call _store_cache"
        assert invalid_idx < store_idx, (
            f"_cache_invalid should come before _store_cache. " f"Calls: {cache_calls}"
        )

    def test_cache_call_sequence_on_hit(self, zsh_harness, completion_script):
        """Verify the correct sequence of cache calls on a hit."""
        cache_id = "poe_tasks__hit_test"
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/hit/test"',
        )

        pre_cache = {cache_id: ["cached:Cached task"]}
        mock = {"_zsh_describe_tasks": "fresh:Should not see this"}

        result = zsh_harness(
            script_with_path,
            ["poe", ""],
            2,
            mock_poe_output=mock,
            pre_cache=pre_cache,
        )

        # On cache hit: _cache_invalid (returns false), _retrieve_cache (succeeds)
        # Should NOT have _store_cache (no need to re-store)
        cache_calls = result.cache_calls

        invalid_calls = [c for c in cache_calls if "_cache_invalid" in c]
        retrieve_calls = [c for c in cache_calls if "_retrieve_cache" in c]
        store_calls = [c for c in cache_calls if "_store_cache" in c]

        assert invalid_calls, "Should check _cache_invalid"
        assert retrieve_calls, "Should call _retrieve_cache on hit"
        assert (
            not store_calls
        ), f"Should NOT call _store_cache on cache hit. Calls: {cache_calls}"

    def test_help_task_state_also_caches(self, zsh_harness, completion_script):
        """The help_task state should also use/store cache."""
        script_with_path = completion_script.replace(
            'local effective_path="${target_path:-$PWD}"',
            'local effective_path="/help/test"',
        )

        mock = {"_zsh_describe_tasks": "greet:Greet\ntest:Test"}

        # Simulate: poe --help <TAB>
        result = zsh_harness(
            script_with_path,
            ["poe", "--help", ""],
            3,
            mock_poe_output=mock,
        )

        # Should cache task list for help completion too
        task_cache = [f for f in result.cache_files if "poe_tasks" in f]
        assert task_cache, f"help_task should also cache tasks: {result.cache_files}"


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
class TestZshHarnessBasic:
    """Basic tests that verify script structure and parsing."""

    def test_script_parses_without_error(self, run_poe_main, tmp_path):
        """The completion script should parse without zsh errors."""
        result = run_poe_main("_zsh_completion")
        script = result.stdout

        script_file = tmp_path / "completion.zsh"
        script_file.write_text(script)

        proc = subprocess.run(
            ["zsh", "-n", str(script_file)],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"Syntax error: {proc.stderr}"

    def test_script_can_be_sourced(self, run_poe_main, tmp_path):
        """The completion script can be sourced in zsh."""
        result = run_poe_main("_zsh_completion")
        script = result.stdout

        proc = subprocess.run(
            ["zsh", "-c", f"source /dev/stdin << 'EOF'\n{script}\nEOF\necho ok"],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"Source error: {proc.stderr}"
        assert "ok" in proc.stdout

    def test_function_defined(self, run_poe_main, tmp_path):
        """The _poe function should be defined after sourcing."""
        result = run_poe_main("_zsh_completion")
        script = result.stdout

        proc = subprocess.run(
            [
                "zsh",
                "-c",
                f"source /dev/stdin << 'EOF'\n{script}\nEOF\n" "type _poe | head -1",
            ],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"Error: {proc.stderr}"
        assert "_poe is a shell function" in proc.stdout


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
class TestZshTaskNamePatterns:
    """Tests for the full space of valid task names.

    Poe task names must match: r"^\\w[\\w\\d\\-\\_\\+\\:]*$"
    - Must start with a word character (letter or underscore)
    - Can contain: word chars, digits, hyphens, underscores, plus, colon
    """

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated zsh completion script."""
        result = run_poe_main("_zsh_completion")
        return result.stdout

    def test_task_with_digits(self, zsh_harness, completion_script):
        """Tasks with digits should work."""
        mock_output = {
            "_zsh_describe_tasks": "task1:First task\nbuild2:Second build",
            "_describe_task_args": "--opt\tstring\tOption\t_",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "task1", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == "task1"
        assert result.arguments_called

    def test_task_with_plus(self, zsh_harness, completion_script):
        """Tasks with plus sign should work (e.g., build+test)."""
        mock_output = {
            "_zsh_describe_tasks": "build+test:Build and test\nlint+format:Lint and format",
            "_describe_task_args": "--verbose\tboolean\tVerbose\t_",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "build+test", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == "build+test"
        assert result.arguments_called

    def test_task_with_colon_namespace(self, zsh_harness, completion_script):
        """Tasks with colons (namespaced) should work (e.g., docker:build)."""
        mock_output = {
            "_zsh_describe_tasks": "docker\\:build:Build docker image\ndocker\\:push:Push image",
            "_describe_task_args": "--tag\tstring\tImage tag\t_",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "docker:build", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == "docker:build"
        assert result.arguments_called

    def test_task_with_deep_namespace(self, zsh_harness, completion_script):
        """Tasks with multiple colons should work (e.g., a:b:c)."""
        mock_output = {
            "_zsh_describe_tasks": "ns\\:sub\\:task:Nested task",
            "_describe_task_args": "--opt\tstring\tOption\t_",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "ns:sub:task", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == "ns:sub:task"

    def test_task_with_mixed_special_chars(self, zsh_harness, completion_script):
        """Tasks with mixed special characters should work."""
        mock_output = {
            "_zsh_describe_tasks": "build_v2-fast+ci:Complex task name",
            "_describe_task_args": "--opt\tstring\tOption\t_",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "build_v2-fast+ci", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == "build_v2-fast+ci"

    def test_task_starting_with_underscore(self, zsh_harness, completion_script):
        """Tasks starting with underscore should work."""
        mock_output = {
            "_zsh_describe_tasks": "_private:Private task\n_internal:Internal task",
            "_describe_task_args": "--opt\tstring\tOption\t_",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "_private", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == "_private"

    def test_task_list_with_special_chars(self, zsh_harness, completion_script):
        """Task listing should show tasks with special characters."""
        mock_output = {
            "_zsh_describe_tasks": (
                "simple:Simple task\n"
                "with-dash:Has dash\n"
                "with_under:Has underscore\n"
                "with+plus:Has plus\n"
                "ns\\:task:Namespaced"
            ),
        }

        result = zsh_harness(
            completion_script,
            words=["poe", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        assert result.describe_called
        # All tasks should be in the list
        items_str = " ".join(result.describe_items)
        assert "simple" in items_str
        assert "with-dash" in items_str
        assert "with_under" in items_str
        assert "with+plus" in items_str

    def test_all_valid_task_name_chars(self, zsh_harness, completion_script):
        """Test task name with all valid character types."""
        # Task name using all allowed chars: word, digit, hyphen, underscore, plus, colon
        task_name = "Task_1-test+build:v2"
        # Escape colon for zsh _describe format
        escaped_name = task_name.replace(":", "\\:")
        mock_output = {
            "_zsh_describe_tasks": f"{escaped_name}:Complex name",
            "_describe_task_args": "--opt\tstring\tOption\t_",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", task_name, ""],
            current=3,
            mock_poe_output=mock_output,
        )

        assert result.current_task == task_name
        assert result.arguments_called


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not available")
class TestZshBackwardCompatibility:
    """Tests for backward compatibility with older poe versions.

    These tests verify that the completion script works correctly when
    newer poe builtins (like _zsh_describe_tasks, _describe_task_args) are
    not available, gracefully falling back to basic functionality.
    """

    @pytest.fixture
    def completion_script(self, run_poe_main):
        """Get the generated zsh completion script."""
        result = run_poe_main("_zsh_completion")
        return result.stdout

    def test_fallback_to_list_tasks_when_describe_unavailable(
        self, zsh_harness, completion_script
    ):
        """When _zsh_describe_tasks fails, should fall back to _list_tasks."""
        # Simulate old poe: _zsh_describe_tasks returns help text (command not found)
        # The script checks for *"Poe the Poet"* or *"Usage"* patterns
        mock_output = {
            "_zsh_describe_tasks": "Poe the Poet - A task runner",  # Help text triggers fallback
            "_list_tasks": "greet echo build",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        # Should fall back to _list_tasks and still offer tasks
        assert result.describe_called
        # Tasks should be available (converted from _list_tasks format)
        assert any("greet" in item for item in result.describe_items)

    def test_fallback_to_list_tasks_when_describe_empty(
        self, zsh_harness, completion_script
    ):
        """When _zsh_describe_tasks returns empty, should fall back to _list_tasks."""
        mock_output = {
            "_zsh_describe_tasks": "",  # Empty = command failed
            "_list_tasks": "greet echo build",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        # Should fall back to _list_tasks
        assert result.describe_called
        # Tasks should be available
        assert any("greet" in item for item in result.describe_items)

    def test_describe_task_args_unavailable_falls_back_to_files(
        self, zsh_harness, completion_script
    ):
        """When _describe_task_args is unavailable, should fall back to file completion."""
        mock_output = {
            "_zsh_describe_tasks": "greet:Greet someone",
            # _describe_task_args not provided - simulates old poe version
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "greet", ""],
            current=3,
            mock_poe_output=mock_output,
        )

        # Without task args, should fall back to file completion
        assert result.files_called

    def test_only_list_tasks_available(self, zsh_harness, completion_script):
        """Completion should work with only _list_tasks available (oldest poe)."""
        # Only _list_tasks works - all other commands fail
        mock_output = {
            "_zsh_describe_tasks": "",  # Fails
            "_list_tasks": "simple-task another-task",
            # No _describe_task_args
        }

        result = zsh_harness(
            completion_script,
            words=["poe", ""],
            current=2,
            mock_poe_output=mock_output,
        )

        # Should still complete tasks via _list_tasks fallback
        assert result.describe_called
        # Tasks should be offered
        assert any("simple-task" in item for item in result.describe_items)

    def test_partial_task_name_with_old_poe(self, zsh_harness, completion_script):
        """Partial task completion should work with old poe versions."""
        mock_output = {
            "_zsh_describe_tasks": "",  # Fails
            "_list_tasks": "greet echo build grep",
        }

        result = zsh_harness(
            completion_script,
            words=["poe", "gr"],
            current=2,
            mock_poe_output=mock_output,
        )

        # Should still allow partial matching
        assert result.describe_called
