# ruff: noqa: E501
"""
Zsh completion harness for testing and debugging.

This module provides tools to test zsh completion scripts by stubbing
zsh builtins (_arguments, _describe, _files) and capturing their calls.

Usage in tests:
    result = zsh_harness(script, words, current, mock_poe_output)
    assert result.state == "task"

Usage for debugging:
    poe zsh-harness /path/to/test.zsh --words "poe task --" --current 4

Harness Limitations:
    The _arguments stub in this harness uses simplified position/previous-word
    logic to determine state, rather than parsing the full _arguments spec like
    real zsh _arguments -C does. This means:

    1. For optional values (::), the harness always sets state based on the
       previous word (e.g., --help -> help_task), but real _arguments may not
       set ANY state when there's ambiguity between an optional value and a
       positional argument.

    2. The completion script includes fallback logic to handle cases where
       _arguments doesn't set state. This fallback manually checks for --help/-h
       and CURRENT position to determine the appropriate state.

    Tests in this harness verify the script's logic works with the harness's
    simplified state detection. Real zsh behavior relies on both _arguments and
    the fallback logic working together.
"""

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


class ZshHarnessResult:
    """Result from running the zsh completion harness."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def _read_file(self, name: str) -> str:
        path = self.output_dir / name
        if path.exists():
            return path.read_text().strip()
        return ""

    def _read_lines(self, name: str) -> list[str]:
        content = self._read_file(name)
        if not content:
            return []
        return content.split("\n")

    @property
    def files_called(self) -> bool:
        return self._read_file("files_called") == "1"

    @property
    def describe_called(self) -> bool:
        return self._read_file("describe_called") == "1"

    @property
    def arguments_called(self) -> bool:
        return self._read_file("arguments_called") == "1"

    @property
    def early_return(self) -> bool:
        """True if _files was called before _arguments (early return path)."""
        return self._read_file("early_return") == "1"

    @property
    def describe_tag(self) -> str:
        """The tag passed to _describe (first argument)."""
        return self._read_file("describe_tag")

    @property
    def describe_items(self) -> list[str]:
        """Items passed to _describe (the array contents)."""
        return self._read_lines("describe_items")

    @property
    def arguments_specs(self) -> list[str]:
        """Argument specs passed to _arguments."""
        return self._read_lines("arguments_specs")

    @property
    def state(self) -> str:
        """The completion state that was entered."""
        return self._read_file("state")

    @property
    def current_task(self) -> str:
        """The detected current task."""
        return self._read_file("current_task")

    @property
    def target_path(self) -> str:
        """The detected target path."""
        return self._read_file("target_path")

    @property
    def after_separator(self) -> bool:
        """Whether -- separator was detected."""
        return self._read_file("after_separator") == "1"

    @property
    def completing_option(self) -> bool:
        """Whether current word starts with - (completing an option)."""
        return self._read_file("completing_option") == "1"

    @property
    def poe_describe_task_args_output(self) -> str:
        """The raw output from poe _describe_task_args (for debugging)."""
        return self._read_file("poe_describe_task_args_output")

    @property
    def arg_specs_count(self) -> int:
        """Number of items in arg_specs array (for debugging)."""
        val = self._read_file("arg_specs_count")
        return int(val) if val.isdigit() else 0

    @property
    def stderr(self) -> str:
        """Captured stderr from zsh execution."""
        return self._read_file("stderr")

    @property
    def stdout(self) -> str:
        """Captured stdout from zsh execution."""
        return self._read_file("stdout")

    @property
    def cache_dir(self) -> Path:
        """Directory where cache files are stored."""
        return self.output_dir / "cache"

    @property
    def cache_files(self) -> list[str]:
        """List of cache file names created during this run."""
        if self.cache_dir.exists():
            return [f.name for f in self.cache_dir.iterdir() if f.is_file()]
        return []

    def get_cache_contents(self, cache_id: str) -> list[str]:
        """Get contents of a specific cache file."""
        cache_file = self.cache_dir / cache_id
        if cache_file.exists():
            content = cache_file.read_text().strip()
            if content:
                return content.split("\n")
        return []

    @property
    def cache_calls(self) -> list[str]:
        """List of cache function calls made during this run."""
        calls_file = self.output_dir / "cache_calls"
        if calls_file.exists():
            content = calls_file.read_text().strip()
            if content:
                return content.split("\n")
        return []

    def summary(self) -> str:
        """Return a human-readable summary of the result."""
        lines = [
            f"state: {self.state or '(none)'}",
            f"current_task: {self.current_task or '(none)'}",
            f"target_path: {self.target_path or '(none)'}",
            f"after_separator: {self.after_separator}",
            f"files_called: {self.files_called}",
            f"describe_called: {self.describe_called}",
            f"arguments_called: {self.arguments_called}",
            f"early_return: {self.early_return}",
            f"arg_specs_count: {self.arg_specs_count}",
        ]
        if self.describe_items:
            lines.append(f"describe_items: {self.describe_items[:3]}...")
        if self.arguments_specs:
            lines.append(f"arguments_specs: {len(self.arguments_specs)} specs")
        if self.cache_files:
            lines.append(f"cache_files: {self.cache_files}")
        if self.cache_calls:
            lines.append(f"cache_calls: {len(self.cache_calls)} calls")
        if self.stderr:
            lines.append(f"stderr: {self.stderr[:100]}...")
        return "\n".join(lines)


@dataclass
class ZshHarnessConfig:
    """Configuration for the zsh harness."""

    words: list[str] = field(default_factory=lambda: ["poe", ""])
    current: int = 2
    mock_poe_output: dict[str, str] = field(default_factory=dict)
    pre_cache: dict[str, list[str]] = field(default_factory=dict)
    debug: bool = False  # If True, add debug output to stderr


def escape_for_shell(value: str) -> str:
    """Escape a string for use in single-quoted shell context."""
    return value.replace("'", "'\"'\"'")


class ZshHarnessBuilder:
    """Builds zsh harness scripts with stubbed builtins."""

    def __init__(self, output_dir: Path, config: ZshHarnessConfig):
        self.output_dir = output_dir
        self.config = config

    def build_stubs(self) -> list[str]:
        """Generate stub functions for zsh completion builtins."""
        debug_prefix = 'echo "[harness]' if self.config.debug else "# "

        lines = [
            "# Output directory for capturing results",
            f'_HARNESS_DIR="{self.output_dir}"',
            "",
            "# Track if _arguments has been called (for early return detection)",
            "_harness_arguments_called=0",
            "",
            "# Stub _files - capture call",
            "function _files {",
            f'    {debug_prefix} _files called" >&2',
            '    echo "1" > "$_HARNESS_DIR/files_called"',
            "    # If _arguments hasn't been called yet, this is an early return",
            '    if [[ "$_harness_arguments_called" == "0" ]]; then',
            '        echo "1" > "$_HARNESS_DIR/early_return"',
            "    fi",
            "}",
            "",
            "# Stub _describe - capture tag and items",
            "function _describe {",
            f'    {debug_prefix} _describe called with: $1" >&2',
            '    echo "1" > "$_HARNESS_DIR/describe_called"',
            '    echo "$1" > "$_HARNESS_DIR/describe_tag"',
            '    local arr_name="$2"',
            '    if [[ -n "$arr_name" ]]; then',
            "        # Write array contents, one per line",
            '        eval "for item in \\${$arr_name[@]}; do echo \\$item; done" > "$_HARNESS_DIR/describe_items"',
            "    fi",
            "}",
            "",
            "# Cache storage (file-based for inspection)",
            "# Creates a cache dir and stubs _cache_invalid, _retrieve_cache, _store_cache",
            '_HARNESS_CACHE_DIR="$_HARNESS_DIR/cache"',
            'mkdir -p "$_HARNESS_CACHE_DIR"',
            "",
            "# Stub _cache_invalid - check if cache is invalid (missing or stale)",
            "function _cache_invalid {",
            '    local cache_id="$1"',
            '    local cache_file="$_HARNESS_CACHE_DIR/$cache_id"',
            "",
            "    # Log the call",
            '    echo "_cache_invalid $cache_id" >> "$_HARNESS_DIR/cache_calls"',
            "",
            "    # Invalid if doesn't exist",
            '    [[ ! -f "$cache_file" ]]',
            "}",
            "",
            "# Stub _retrieve_cache - retrieve cached data into a variable",
            "function _retrieve_cache {",
            '    local cache_id="$1"',
            '    local var_name="$2"',
            '    local cache_file="$_HARNESS_CACHE_DIR/$cache_id"',
            "",
            '    echo "_retrieve_cache $cache_id $var_name" >> "$_HARNESS_DIR/cache_calls"',
            "",
            '    if [[ -f "$cache_file" ]]; then',
            "        # Read array from file (one element per line)",
            "        # Use loop to preserve elements with spaces/colons",
            "        local -a _tmp_arr",
            '        while IFS= read -r line || [[ -n "$line" ]]; do',
            "            # Skip empty lines to avoid array with empty element",
            '            [[ -n "$line" ]] && _tmp_arr+=("$line")',
            '        done < "$cache_file"',
            "        # Set the variable (may be empty array)",
            "        if (( ${#_tmp_arr[@]} > 0 )); then",
            '            eval "$var_name=(\\"\\"\\${_tmp_arr[@]}\\"\\")"',
            "        else",
            '            eval "$var_name=()"',
            "        fi",
            "        return 0",
            "    fi",
            "    return 1",
            "}",
            "",
            "# Stub _store_cache - store variable data to cache",
            "function _store_cache {",
            '    local cache_id="$1"',
            '    local var_name="$2"',
            '    local cache_file="$_HARNESS_CACHE_DIR/$cache_id"',
            "",
            '    echo "_store_cache $cache_id $var_name" >> "$_HARNESS_DIR/cache_calls"',
            "",
            "    # Write array to file (one element per line)",
            '    eval "printf \'%s\\\\n\' \\"\\${${var_name}[@]}\\"" > "$cache_file"',
            "}",
            "",
            "# Stub _arguments - capture specs and set state",
            "# This simulates real _arguments -C behavior:",
            "#   - When current word starts with -, options are offered",
            "#   - State is set based on positional specs regardless",
            "function _arguments {",
            "    _harness_arguments_called=1",
            f'    {debug_prefix} _arguments called with $# args" >&2',
            '    echo "1" > "$_HARNESS_DIR/arguments_called"',
            "    # Write each argument spec on its own line",
            '    for arg in "$@"; do',
            '        echo "$arg"',
            '    done > "$_HARNESS_DIR/arguments_specs"',
            "",
            "    # Track if current word looks like an option (starts with -)",
            "    # Real _arguments offers options when word starts with -",
            '    local cur="${words[CURRENT]}"',
            '    if [[ "$cur" == -* ]]; then',
            '        echo "1" > "$_HARNESS_DIR/completing_option"',
            f'        {debug_prefix} completing option: $cur" >&2',
            "    fi",
            "",
            "    # Determine state based on CURRENT position",
            "    # NOTE: Real _arguments -C can set MULTIPLE space-separated states",
            "    # when there's ambiguity (e.g., optional option value vs positional)",
            '    local prev="${words[CURRENT-1]}"',
            "    # --help has optional value AND position could be first positional",
            "    # Real zsh sets both states in this ambiguous case",
            '    if [[ "$prev" == "-h" || "$prev" == "--help" ]]; then',
            '        state="help_task task"  # Both states - matches real zsh behavior',
            '        echo "$state" > "$_HARNESS_DIR/state"',
            "        return",
            "    fi",
            "    # Position 2 = completing task name (but may also complete options)",
            "    if (( CURRENT == 2 )); then",
            '        state="task"',
            '        echo "$state" > "$_HARNESS_DIR/state"',
            "        return",
            "    fi",
            "    # Position > 2 = completing task args",
            "    if (( CURRENT > 2 )); then",
            '        state="args"',
            '        echo "$state" > "$_HARNESS_DIR/state"',
            "        return",
            "    fi",
            "}",
        ]
        return lines

    def build_mock_poe(self) -> list[str]:
        """Generate mock poe command function."""
        debug_prefix = 'echo "[harness]' if self.config.debug else "# "

        lines = [
            "",
            "# Mock poe command",
            "function poe {",
            '    local cmd="$1"',
            f'    {debug_prefix} poe called with: $*" >&2',
            '    case "$cmd" in',
        ]

        for cmd_suffix, output in self.config.mock_poe_output.items():
            escaped_output = escape_for_shell(output)
            lines.extend(
                [
                    f"        {cmd_suffix})",
                    "            shift",
                    f"            echo '{escaped_output}'",
                    "            ;;",
                ]
            )

        lines.extend(
            [
                "        *)",
                "            # Unknown command - return empty",
                "            ;;",
                "    esac",
                "}",
            ]
        )
        return lines

    def build_context(self) -> list[str]:
        """Generate the completion context (words array and CURRENT)."""
        lines = [
            "",
            "# Set up completion context",
            "typeset -a words",
        ]

        # Add words array (zsh arrays are 1-indexed)
        for i, word in enumerate(self.config.words):
            escaped_word = escape_for_shell(word)
            lines.append(f"words[{i + 1}]='{escaped_word}'")

        lines.extend(
            [
                "",
                f"CURRENT={self.config.current}",
            ]
        )
        return lines

    def instrument_script(self, script: str) -> str:
        """Add instrumentation to capture state from the completion script."""
        modified = script

        # Capture state variables right before the early return check
        early_capture = """
    # Harness: capture state before early return
    echo "$after_separator" > "$_HARNESS_DIR/after_separator"
    echo "$current_task" > "$_HARNESS_DIR/current_task"
    echo "$target_path" > "$_HARNESS_DIR/target_path"
"""
        modified = modified.replace(
            "# After --, only offer file completions",
            early_capture + "\n    # After --, only offer file completions",
        )

        # Add debug output to the while loop if debug mode
        if self.config.debug:
            # Debug after reading each line in the while loop
            modified = modified.replace(
                '[[ -z "$opts" ]] && continue',
                '[[ -z "$opts" ]] && continue\n'
                '                echo "[harness] Read: opts=$opts type=$arg_type help=$help_text choices=$choices" >&2',
            )
            # Debug after used option check
            modified = modified.replace(
                "(( total_count >= 1 )) && continue",
                '(( total_count >= 1 )) && { echo "[harness] SKIP $opts: already used (count=$total_count)" >&2; continue; }',
            )
            # Debug when adding to arg_specs
            modified = modified.replace(
                "arg_specs+=(",
                'echo "[harness] ADD to arg_specs" >&2; arg_specs+=(',
            )

        # Capture poe _describe_task_args output for debugging
        poe_output_capture = """
            # Harness: capture poe output for debugging
            poe _describe_task_args "$current_task" $target_path 2>/dev/null > "$_HARNESS_DIR/poe_describe_task_args_output"
            echo "${#arg_specs[@]}" > "$_HARNESS_DIR/arg_specs_count"
"""
        modified = modified.replace(
            "# Fallback to _files if no args defined",
            poe_output_capture
            + "\n            # Fallback to _files if no args defined",
        )

        # Capture state variable before the case statement
        state_capture = """
    # Harness: capture state variable
    echo "$state" > "$_HARNESS_DIR/state"
"""
        modified = modified.replace(
            "case $state in", state_capture + "\n    case $state in"
        )

        return modified

    def build_full_harness(self, script: str) -> str:
        """Build the complete harness script."""
        parts = [
            *self.build_stubs(),
            *self.build_mock_poe(),
            *self.build_context(),
            "",
            "# The completion script:",
            self.instrument_script(script),
            "",
            "# Call the completion function",
            "_poe",
        ]
        return "\n".join(parts)


class ZshHarnessRunner:
    """Executes zsh harness scripts and captures results."""

    def __init__(self, work_dir: Path | None = None):
        self.work_dir = work_dir
        self._temp_dir = None
        self._run_counter = 0

    def __enter__(self):
        if self.work_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory()
            self.work_dir = Path(self._temp_dir.name)
        return self

    def __exit__(self, *args):
        if self._temp_dir:
            self._temp_dir.cleanup()

    def run(
        self,
        script: str,
        config: ZshHarnessConfig,
    ) -> ZshHarnessResult:
        """
        Run a zsh completion script with the harness.

        Args:
            script: The zsh completion script to test
            config: Harness configuration

        Returns:
            ZshHarnessResult with captured completion behavior
        """
        assert self.work_dir is not None, "Runner not initialized (use context manager)"

        # Use unique output directory for each run to avoid interference
        self._run_counter += 1
        output_dir = self.work_dir / f"harness_output_{self._run_counter}"
        output_dir.mkdir(exist_ok=True)

        # Set up pre-populated cache if provided
        if config.pre_cache:
            cache_dir = output_dir / "cache"
            cache_dir.mkdir(exist_ok=True)
            for cache_id, contents in config.pre_cache.items():
                (cache_dir / cache_id).write_text("\n".join(contents))

        # Build the harness
        builder = ZshHarnessBuilder(output_dir, config)
        harness_script = builder.build_full_harness(script)

        # Write harness script to file for debugging
        harness_file = output_dir / "harness.zsh"
        harness_file.write_text(harness_script)

        # Run zsh with the harness
        result = subprocess.run(
            ["zsh", str(harness_file)],
            capture_output=True,
            text=True,
            cwd=self.work_dir,
        )

        # Save stdout/stderr for debugging
        (output_dir / "stdout").write_text(result.stdout)
        (output_dir / "stderr").write_text(result.stderr)
        (output_dir / "returncode").write_text(str(result.returncode))

        return ZshHarnessResult(output_dir)


def run_harness(
    script: str,
    words: list[str],
    current: int,
    mock_poe_output: dict[str, str] | None = None,
    pre_cache: dict[str, list[str]] | None = None,
    debug: bool = False,
    work_dir: Path | None = None,
) -> ZshHarnessResult:
    """
    Convenience function to run the zsh harness.

    Args:
        script: The zsh completion script to test
        words: Command line words (e.g., ["poe", "task", "--opt"])
        current: Index of current word being completed (1-based for zsh)
        mock_poe_output: Dict mapping command suffixes to output
        pre_cache: Dict mapping cache IDs to pre-populated cache contents
        debug: If True, print debug output to stderr
        work_dir: Optional working directory (temp dir created if None)

    Returns:
        ZshHarnessResult with captured completion behavior
    """
    config = ZshHarnessConfig(
        words=words,
        current=current,
        mock_poe_output=mock_poe_output or {},
        pre_cache=pre_cache or {},
        debug=debug,
    )

    with ZshHarnessRunner(work_dir) as runner:
        return runner.run(script, config)


def task_zsh_harness(path: str):
    """
    Poe task to run zsh code through the completion harness for debugging.

    Usage:
        poe zsh-harness /path/to/test.zsh
        poe zsh-harness -  # read from stdin

    The test file should contain zsh code that will be run through the harness.
    The file can optionally include special comments to configure the harness:

        # WORDS: poe task --opt
        # CURRENT: 4
        # MOCK _zsh_describe_tasks: task1:desc1
        # MOCK _describe_task_args: --opt\\tstring\\thelp\\t_
    """
    import sys

    from poethepoet.completion.zsh import get_zsh_completion_script

    if path == "-":
        content = sys.stdin.read()
    else:
        test_file = Path(path)
        if not test_file.exists():
            print(f"Error: File not found: {path}")
            return 1
        content = test_file.read_text()

    # Parse configuration from file comments
    words = ["poe", ""]
    current = 2
    mock_poe_output: dict[str, str] = {}

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# WORDS:"):
            words = line[8:].strip().split()
        elif line.startswith("# CURRENT:"):
            current = int(line[10:].strip())
        elif line.startswith("# MOCK "):
            # Format: # MOCK _cmd_name: output
            rest = line[7:]
            cmd, _, output = rest.partition(":")
            if cmd and output:
                # Handle escape sequences
                mock_poe_output[cmd.strip()] = (
                    output.strip().encode().decode("unicode_escape")
                )

    # Determine what to test
    if content.strip().startswith("#compdef"):
        # It's a full completion script
        script = content
    elif "function _poe" in content:
        # It's a completion function
        script = content
    else:
        # Assume it's a fragment - use the full generated script
        script = get_zsh_completion_script()
        print("Using generated completion script")

    print("Running harness with:")
    print(f"  words: {words}")
    print(f"  current: {current}")
    print(f"  mock_poe_output: {list(mock_poe_output.keys())}")
    print()

    # Create a persistent temp dir for inspection
    import tempfile

    with tempfile.TemporaryDirectory(prefix="zsh_harness_") as tmpdir:
        work_dir = Path(tmpdir)
        result = run_harness(
            script=script,
            words=words,
            current=current,
            mock_poe_output=mock_poe_output,
            debug=True,
            work_dir=work_dir,
        )

        print("=== Result Summary ===")
        print(result.summary())
        print()

        if result.stderr:
            print("=== Stderr (debug output) ===")
            print(result.stderr)
            print()

        if result.arguments_specs:
            print("=== Arguments Specs (first 10) ===")
            for spec in result.arguments_specs[:10]:
                print(f"  {spec}")
            if len(result.arguments_specs) > 10:
                print(f"  ... and {len(result.arguments_specs) - 10} more")
            print()

        # Print path to harness files for further inspection
        print("=== Files for inspection ===")
        print(f"  Harness script: {work_dir / 'harness.zsh'}")
        print(f"  Output dir: {work_dir / 'harness_output'}")
        print()
        print("(Files will be deleted when this command exits)")

        # Keep temp dir alive for interactive inspection
        input("Press Enter to exit and clean up temp files...")

    return 0
