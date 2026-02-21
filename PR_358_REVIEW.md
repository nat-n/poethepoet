# PR #358 Review: PowerShell Completions

## Summary

This PR adds PowerShell tab-completion support to poethepoet, covering global CLI
options, task names, task-specific arguments/options, positional arguments with choices,
and directory/executor value completion. Authored by NSPC911 with enhancements from
the maintainer (nat-n). Also includes two unrelated base commits (Python 3.14 support,
zsh caching improvements).

## Changed Files

| File | Change | Lines |
|------|--------|-------|
| `poethepoet/completion/powershell.py` | NEW | ~423 |
| `poethepoet/__init__.py` | Modified | +6 |
| `tests/completion/test_powershell_completion.py` | NEW | ~1504 |
| `docs/installation.rst` | Modified | +18 |
| (+ unrelated: zsh.py, CI, test flakiness fixes) | | |

## Strengths

### 1. Solid PowerShell Completion Architecture
- Uses `Register-ArgumentCompleter -Native` — the correct API for both Windows
  PowerShell 5.1 and PowerShell Core (pwsh 7+)
- Leverages shared builtins (`_list_tasks`, `_describe_task_args`) for dynamic data
- Global option exclusion map introspects argparse's `_mutually_exclusive_groups` and
  action types, correctly handling:
  - Repeatable actions (`_CountAction`, `_AppendAction`) that shouldn't self-exclude
  - Mutual exclusion groups (`-v`/`-q`, `--ansi`/`--no-ansi`)
- More sophisticated option filtering than bash completion
- Positional argument tracking correctly handles the PowerShell quirk where
  `Where-Object` returns a scalar (not 1-element array) — fixed with `@()` wrapper
- `$prevWord` calculation handles `CommandElements` not including empty `$wordToComplete`

### 2. Clean Integration
The 6-line addition to `__init__.py` follows the exact same pattern as bash/zsh/fish.

### 3. Comprehensive Test Suite (~1500 lines)
Well-organized test classes covering:
- Script structure regression tests
- PowerShell syntax validation
- Integration tests (dot-sourcing, function existence, variable definitions)
- Unit tests for each helper function via real PowerShell subprocess
- Edge cases: empty tasks, special characters, graceful failures, option group filtering
- Proper `@pytest.mark.skipif` guards when PowerShell isn't available

### 4. Documentation
Clear `installation.rst` additions with correct invocation and profile reload tip.

## Issues and Suggestions

### Medium Priority

**Hardcoded executor choices**: Both `powershell.py` and `bash.py` hardcode
`@('auto', 'poetry', 'simple', 'uv', 'virtualenv')`. Should ideally pull from a
shared source. Pre-existing tech debt, not a blocker for this PR.

### Nits

- **`# noqa: E501`** at the end of `powershell.py` — the file-level
  `# ruff: noqa: E501` approach (as used in the test file) is arguably cleaner.
- **Unrelated changes** from two base commits (zsh caching, Python 3.14 support) add
  noise to the diff but are no-ops on merge.

## Security

- `name` parameter validated by `isalnum()` in `_run_builtin_task` — no injection risk
- Error output suppressed with `2>$null` and `try/catch` — graceful failure tested
- No `$ErrorActionPreference` override — default "Continue" behavior is appropriate

## Verdict

**Ready to merge with minor nits.** The implementation is well-structured, follows
existing patterns, handles edge cases thoughtfully, and has comprehensive test coverage.
Feature parity with bash completion (and beyond fish's simpler implementation).
