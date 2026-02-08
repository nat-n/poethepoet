"""
Bash completion harness for testing and debugging.

This module provides tools to test bash completion scripts by stubbing
bash builtins (_init_completion, compgen, _filedir) and capturing their calls.

Usage in tests:
    result = bash_harness(script, words, current, mock_poe_output)
    assert "greet" in result.compreply

Usage for debugging:
    poe bash-harness -

Key differences from Zsh:
    - Array indexing is 0-based (COMP_CWORD)
    - Completion output uses COMPREPLY array
    - File completion uses _filedir or compgen -f
    - Word array uses COMP_WORDS
    - No caching support (too complex for bash)
"""

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


class BashHarnessResult:
    """Result from running the bash completion harness."""

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

    # Core output
    @property
    def compreply(self) -> list[str]:
        """Final completions offered (COMPREPLY array contents)."""
        return self._read_lines("compreply")

    # Stub tracking
    @property
    def compgen_called(self) -> bool:
        """Was compgen invoked."""
        return self._read_file("compgen_called") == "1"

    @property
    def compgen_calls(self) -> list[str]:
        """All compgen invocations."""
        return self._read_lines("compgen_calls")

    @property
    def filedir_called(self) -> bool:
        """Was _filedir invoked."""
        return self._read_file("filedir_called") == "1"

    @property
    def init_completion_called(self) -> bool:
        """Was _init_completion invoked."""
        return self._read_file("init_completion_called") == "1"

    # Poe helper tracking
    @property
    def poe_calls(self) -> list[str]:
        """All poe invocations."""
        return self._read_lines("poe_calls")

    @property
    def list_tasks_called(self) -> bool:
        """Was _list_tasks called."""
        calls = self.poe_calls
        return any("_list_tasks" in c for c in calls)

    @property
    def task_args_called(self) -> bool:
        """Was task args fetched (via _describe_task_args)."""
        calls = self.poe_calls
        return any("_describe_task_args" in c for c in calls)

    # State detection
    @property
    def detected_task(self) -> str:
        """Task name found."""
        return self._read_file("detected_task")

    @property
    def detected_target_path(self) -> str:
        """Path from -C/--directory."""
        return self._read_file("detected_target_path")

    @property
    def task_position(self) -> int:
        """Position of task in words."""
        val = self._read_file("task_position")
        return int(val) if val.isdigit() else -1

    @property
    def cur(self) -> str:
        """Current word being completed."""
        return self._read_file("cur")

    @property
    def prev(self) -> str:
        """Previous word."""
        return self._read_file("prev")

    @property
    def show_task_opts(self) -> bool:
        """Boolean flag detected for showing task options."""
        return self._read_file("show_task_opts") == "true"

    # Execution
    @property
    def stdout(self) -> str:
        """Captured stdout from bash execution."""
        return self._read_file("stdout")

    @property
    def stderr(self) -> str:
        """Captured stderr from bash execution."""
        return self._read_file("stderr")

    @property
    def returncode(self) -> int:
        """Return code from bash execution."""
        val = self._read_file("returncode")
        return int(val) if val.lstrip("-").isdigit() else -1

    def summary(self) -> str:
        """Return a human-readable summary of the result."""
        suffix = "..." if len(self.compreply) > 5 else ""
        lines = [
            f"compreply: {self.compreply[:5]}{suffix}",
            f"detected_task: {self.detected_task or '(none)'}",
            f"detected_target_path: {self.detected_target_path or '(none)'}",
            f"task_position: {self.task_position}",
            f"cur: {self.cur!r}",
            f"prev: {self.prev!r}",
            f"show_task_opts: {self.show_task_opts}",
            f"compgen_called: {self.compgen_called}",
            f"filedir_called: {self.filedir_called}",
            f"init_completion_called: {self.init_completion_called}",
            f"list_tasks_called: {self.list_tasks_called}",
            f"task_args_called: {self.task_args_called}",
        ]
        if self.poe_calls:
            lines.append(f"poe_calls: {self.poe_calls}")
        if self.compgen_calls:
            lines.append(f"compgen_calls: {self.compgen_calls[:3]}...")
        if self.stderr:
            lines.append(f"stderr: {self.stderr[:100]}...")
        return "\n".join(lines)


@dataclass
class BashHarnessConfig:
    """Configuration for the bash harness."""

    words: list[str] = field(default_factory=lambda: ["poe", ""])
    current: int = 1  # 0-based for bash (COMP_CWORD)
    mock_poe_output: dict[str, str] = field(default_factory=dict)
    mock_files: list[str] = field(default_factory=list)
    debug: bool = False


def escape_for_shell(value: str) -> str:
    """Escape a string for use in single-quoted shell context."""
    return value.replace("'", "'\"'\"'")


class BashHarnessBuilder:
    """Builds bash harness scripts with stubbed builtins."""

    def __init__(self, output_dir: Path, config: BashHarnessConfig):
        self.output_dir = output_dir
        self.config = config

    def build_stubs(self) -> list[str]:
        """Generate stub functions for bash completion builtins."""
        debug_prefix = 'echo "[harness]' if self.config.debug else "# "

        # Build mock files array for _filedir
        mock_files_str = " ".join(
            f"'{escape_for_shell(f)}'" for f in self.config.mock_files
        )

        lines = [
            "#!/usr/bin/env bash",
            "",
            "# Output directory for capturing results",
            f'_HARNESS_DIR="{self.output_dir}"',
            "",
            "# Mock files for _filedir",
            f"_MOCK_FILES=({mock_files_str})",
            "",
            "# Stub _init_completion - mark called and set up completion variables",
            "_init_completion() {",
            f'    {debug_prefix} _init_completion called" >&2',
            '    echo "1" > "$_HARNESS_DIR/init_completion_called"',
            "    # Set up completion variables like real _init_completion does",
            '    cur="${COMP_WORDS[COMP_CWORD]}"',
            '    prev="${COMP_WORDS[COMP_CWORD-1]}"',
            '    words=("${COMP_WORDS[@]}")',
            "    cword=$COMP_CWORD",
            "    COMPREPLY=()",
            "    return 0",
            "}",
            "",
            "# Stub compgen - parse options and return filtered matches",
            "compgen() {",
            f'    {debug_prefix} compgen called with: $*" >&2',
            '    echo "1" > "$_HARNESS_DIR/compgen_called"',
            '    echo "compgen $*" >> "$_HARNESS_DIR/compgen_calls"',
            "",
            '    local wordlist=""',
            '    local pattern=""',
            '    local mode=""',
            "",
            "    # Parse compgen arguments",
            "    while [[ $# -gt 0 ]]; do",
            '        case "$1" in',
            "            -W)",
            '                mode="wordlist"',
            '                wordlist="$2"',
            "                shift 2",
            "                ;;",
            "            -f)",
            '                mode="files"',
            "                shift",
            "                ;;",
            "            --)",
            "                shift",
            '                pattern="$1"',
            "                shift",
            "                ;;",
            "            -*)",
            "                # Skip unknown options",
            "                shift",
            "                ;;",
            "            *)",
            '                pattern="$1"',
            "                shift",
            "                ;;",
            "        esac",
            "    done",
            "",
            '    if [[ "$mode" == "wordlist" ]]; then',
            "        # Filter wordlist by pattern",
            "        for word in $wordlist; do",
            '            if [[ -z "$pattern" ]] || [[ "$word" == "$pattern"* ]]; then',
            '                echo "$word"',
            "            fi",
            "        done",
            '    elif [[ "$mode" == "files" ]]; then',
            "        # Return mock files filtered by pattern",
            '        for f in "${_MOCK_FILES[@]}"; do',
            '            if [[ -z "$pattern" ]] || [[ "$f" == "$pattern"* ]]; then',
            '                echo "$f"',
            "            fi",
            "        done",
            "    fi",
            "}",
            "",
            "# Stub _filedir - set COMPREPLY to mock files",
            "_filedir() {",
            f'    {debug_prefix} _filedir called with: $*" >&2',
            '    echo "1" > "$_HARNESS_DIR/filedir_called"',
            "",
            '    local pattern="${cur:-}"',
            "    COMPREPLY=()",
            '    for f in "${_MOCK_FILES[@]}"; do',
            '        if [[ -z "$pattern" ]] || [[ "$f" == "$pattern"* ]]; then',
            '            COMPREPLY+=("$f")',
            "        fi",
            "    done",
            "}",
            "",
        ]
        return lines

    def build_mock_poe(self) -> list[str]:
        """Generate mock poe command function."""
        debug_prefix = 'echo "[harness]' if self.config.debug else "# "

        lines = [
            "# Mock poe command",
            "poe() {",
            '    echo "poe $*" >> "$_HARNESS_DIR/poe_calls"',
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

        # Auto-generate _describe_task_args from _bash_describe_task_args
        # if not provided. This maintains backward compat with existing tests
        if (
            "_bash_describe_task_args" in self.config.mock_poe_output
            and "_describe_task_args" not in self.config.mock_poe_output
        ):
            bash_args = self.config.mock_poe_output["_bash_describe_task_args"]
            # Convert space-separated options to tab-separated format
            # Format: opts\ttype\thelp\tchoices
            task_args_lines = [f"{opt}\\tstring\\t \\t_" for opt in bash_args.split()]
            task_args_output = "\\n".join(task_args_lines)
            lines.extend(
                [
                    "        _describe_task_args)",
                    "            shift",
                    f'            echo -e "{task_args_output}"',
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
        """Generate the completion context (COMP_WORDS array and COMP_CWORD)."""
        lines = [
            "",
            "# Set up completion context",
            "COMP_WORDS=()",
        ]

        # Add words array (bash arrays are 0-indexed)
        for i, word in enumerate(self.config.words):
            escaped_word = escape_for_shell(word)
            lines.append(f"COMP_WORDS[{i}]='{escaped_word}'")

        lines.extend(
            [
                "",
                f"COMP_CWORD={self.config.current}",
                "",
            ]
        )
        return lines

    def instrument_script(self, script: str) -> str:
        """Add instrumentation to capture state from the completion script."""
        modified = script

        # Capture cur and prev after the _init_completion block (and fallback)
        cur_prev_capture = """
    # Harness: capture cur and prev
    echo "$cur" > "$_HARNESS_DIR/cur"
    echo "$prev" > "$_HARNESS_DIR/prev"
"""
        # Insert after the _init_completion fallback block
        modified = modified.replace(
            "cword=$COMP_CWORD\n    }",
            "cword=$COMP_CWORD\n    }\n" + cur_prev_capture,
        )

        # Capture target_path after extraction
        target_path_capture = """
    # Harness: capture target_path
    echo "$target_path" > "$_HARNESS_DIR/detected_target_path"
"""
        # Insert after the for loop that extracts target_path
        modified = modified.replace(
            "# Complete global option values (early return)",
            target_path_capture
            + "\n    # Complete global option values (early return)",
        )

        # Capture task position and potential_task
        task_capture = """
                    # Harness: capture task info
                    echo "$task_position" > "$_HARNESS_DIR/task_position"
                    echo "$potential_task" > "$_HARNESS_DIR/detected_task"
"""
        modified = modified.replace(
            'potential_task="${words[i]}"',
            'potential_task="${words[i]}"\n' + task_capture,
        )

        # Capture show_task_opts
        show_opts_capture = """
            # Harness: capture show_task_opts
            echo "$show_task_opts" > "$_HARNESS_DIR/show_task_opts"
"""
        modified = modified.replace(
            "# Show task options if cur starts with",
            show_opts_capture + "\n    # Show task options if cur starts with",
        )

        # Replace all 'return' statements with COMPREPLY capture + return
        # This ensures we capture COMPREPLY at every exit point
        compreply_capture_return = (
            'printf \'%s\\n\' "${COMPREPLY[@]}" > "$_HARNESS_DIR/compreply"; return'
        )
        modified = modified.replace(
            "            return\n",
            f"            {compreply_capture_return}\n",
        )
        modified = modified.replace(
            "        return\n",
            f"        {compreply_capture_return}\n",
        )

        # Capture COMPREPLY at the very end of the function (for fallback path)
        compreply_capture = """
    # Harness: capture final COMPREPLY
    printf '%s\\n' "${COMPREPLY[@]}" > "$_HARNESS_DIR/compreply"
"""
        # Add at the very end of the function
        modified = modified.replace(
            '_filedir 2>/dev/null || COMPREPLY=($(compgen -f -- "$cur"))\n}',
            '_filedir 2>/dev/null || COMPREPLY=($(compgen -f -- "$cur"))\n'
            + compreply_capture
            + "}",
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
            "_poe_complete",
            "",
            "# Capture final COMPREPLY if not already captured",
            'if [[ ! -f "$_HARNESS_DIR/compreply" ]]; then',
            '    printf \'%s\\n\' "${COMPREPLY[@]}" > "$_HARNESS_DIR/compreply"',
            "fi",
        ]
        return "\n".join(parts)


class BashHarnessRunner:
    """Executes bash harness scripts and captures results."""

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
        config: BashHarnessConfig,
    ) -> BashHarnessResult:
        """
        Run a bash completion script with the harness.

        Args:
            script: The bash completion script to test
            config: Harness configuration

        Returns:
            BashHarnessResult with captured completion behavior
        """
        assert self.work_dir is not None, "Runner not initialized (use context manager)"

        # Use unique output directory for each run to avoid interference
        self._run_counter += 1
        output_dir = self.work_dir / f"harness_output_{self._run_counter}"
        output_dir.mkdir(exist_ok=True)

        # Build the harness
        builder = BashHarnessBuilder(output_dir, config)
        harness_script = builder.build_full_harness(script)

        # Write harness script to file for debugging
        harness_file = output_dir / "harness.bash"
        harness_file.write_text(harness_script)

        # Run bash with the harness
        result = subprocess.run(
            ["bash", str(harness_file)],
            capture_output=True,
            text=True,
            cwd=self.work_dir,
        )

        # Save stdout/stderr for debugging
        (output_dir / "stdout").write_text(result.stdout)
        (output_dir / "stderr").write_text(result.stderr)
        (output_dir / "returncode").write_text(str(result.returncode))

        return BashHarnessResult(output_dir)


def run_harness(
    script: str,
    words: list[str],
    current: int,
    mock_poe_output: dict[str, str] | None = None,
    mock_files: list[str] | None = None,
    debug: bool = False,
    work_dir: Path | None = None,
) -> BashHarnessResult:
    """
    Convenience function to run the bash harness.

    Args:
        script: The bash completion script to test
        words: Command line words (e.g., ["poe", "task", "--opt"])
        current: Index of current word being completed (0-based for bash)
        mock_poe_output: Dict mapping command suffixes to output
        mock_files: List of mock files for file completion
        debug: If True, print debug output to stderr
        work_dir: Optional working directory (temp dir created if None)

    Returns:
        BashHarnessResult with captured completion behavior
    """
    config = BashHarnessConfig(
        words=words,
        current=current,
        mock_poe_output=mock_poe_output or {},
        mock_files=mock_files or [],
        debug=debug,
    )

    with BashHarnessRunner(work_dir) as runner:
        return runner.run(script, config)


def task_bash_harness(path: str):
    """
    Poe task to run bash code through the completion harness for debugging.

    Usage:
        poe bash-harness /path/to/test.bash
        poe bash-harness -  # read from stdin

    The test file should contain bash code that will be run through the harness.
    The file can optionally include special comments to configure the harness:

        # WORDS: poe task --opt
        # CURRENT: 3
        # MOCK _list_tasks: task1 task2
        # MOCK _bash_describe_task_args: --opt1 --opt2
        # FILES: file1.txt file2.py
    """
    import sys

    from poethepoet.completion.bash import get_bash_completion_script

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
    current = 1
    mock_poe_output: dict[str, str] = {}
    mock_files: list[str] = []

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
        elif line.startswith("# FILES:"):
            mock_files = line[8:].strip().split()

    # Determine what to test
    if "_poe_complete()" in content:
        # It's a full completion script
        script = content
    else:
        # Assume it's a fragment - use the full generated script
        script = get_bash_completion_script()
        print("Using generated completion script")

    print("Running harness with:")
    print(f"  words: {words}")
    print(f"  current: {current}")
    print(f"  mock_poe_output: {list(mock_poe_output.keys())}")
    print(f"  mock_files: {mock_files}")
    print()

    # Create a persistent temp dir for inspection
    with tempfile.TemporaryDirectory(prefix="bash_harness_") as tmpdir:
        work_dir = Path(tmpdir)
        result = run_harness(
            script=script,
            words=words,
            current=current,
            mock_poe_output=mock_poe_output,
            mock_files=mock_files,
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

        if result.compreply:
            print("=== COMPREPLY (completions) ===")
            for comp in result.compreply[:20]:
                print(f"  {comp}")
            if len(result.compreply) > 20:
                print(f"  ... and {len(result.compreply) - 20} more")
            print()

        # Print path to harness files for further inspection
        print("=== Files for inspection ===")
        # Find the most recent output dir
        output_dirs = sorted(work_dir.glob("harness_output_*"))
        if output_dirs:
            output_dir = output_dirs[-1]
            print(f"  Harness script: {output_dir / 'harness.bash'}")
            print(f"  Output dir: {output_dir}")
        print()
        print("(Files will be deleted when this command exits)")

        # Keep temp dir alive for interactive inspection
        input("Press Enter to exit and clean up temp files...")

    return 0
