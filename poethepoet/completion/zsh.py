# ruff: noqa: E501
"""
Zsh shell completion script generation for poethepoet.

The completion script is generated dynamically from the argparse configuration
and uses zsh's _arguments and _describe completion functions.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from argparse import Action
    from collections.abc import Iterable


# Zsh code for detecting target directory and current task from command line
# Must run BEFORE _arguments since $words gets modified in state handlers
_TARGET_PATH_LOGIC = """
    local DIR_ARGS=("-C" "--directory" "--root")
    # Other options that take a value (must skip their value when finding task name)
    local VALUE_OPTS=("-e" "--executor" "-h" "--help" "-X" "--executor-opt")

    local target_path=""
    local current_task=""
    local after_separator=0

    # In-memory cache fallback (used when disk cache not enabled)
    (( ${+_poe_mem_tasks} )) || typeset -gA _poe_mem_tasks
    (( ${+_poe_mem_args} )) || typeset -gA _poe_mem_args
    # Timestamps for in-memory cache TTL (using $SECONDS)
    (( ${+_poe_mem_tasks_time} )) || typeset -gA _poe_mem_tasks_time
    (( ${+_poe_mem_args_time} )) || typeset -gA _poe_mem_args_time
    # Hit counters for max cache hits (force refresh after N hits)
    (( ${+_poe_cache_hits_tasks} )) || typeset -gA _poe_cache_hits_tasks
    (( ${+_poe_cache_hits_args} )) || typeset -gA _poe_cache_hits_args

    # Set cache policy for poe completions (1 hour TTL)
    # Use wildcard pattern scoped to command name (${0#_} strips leading _ from
    # function name _poe -> poe). Must not use ${curcontext} because _arguments -C
    # modifies curcontext when entering states (e.g. poe -> poe-args), so a literal
    # context set here won't match the modified context when _cache_invalid looks
    # it up later. The trailing * in ${0#_}* matches these state suffixes.
    zstyle ":completion:*:${0#_}*:*" cache-policy _poe_caching_policy

    # Find target_path from -C/--directory/--root, potential task, and -- separator
    for ((i=2; i<${#words[@]}; i++)); do
        if [[ "${words[i]}" == "--" ]]; then
            after_separator=1
            break
        fi
        if (( $DIR_ARGS[(Ie)${words[i]}] )); then
            if (( ($i+1) >= ${#words[@]} )); then
                _files
                return
            fi
            target_path="${words[i+1]}"
            i=$i+1
        elif (( $VALUE_OPTS[(Ie)${words[i]}] )); then
            # Skip the value for this option (don't treat it as task name)
            i=$i+1
        elif [[ "${words[i]}" != -* && -z "$current_task" ]]; then
            # First non-option word is potential task (validated later if needed)
            current_task="${words[i]}"
        fi
    done

    # After --, only offer file completions (pass-through args to task)
    if (( after_separator )); then
        _files
        return
    fi
"""


def _get_describe_task_args_completion(name: str) -> str:
    """
    Generate zsh code for task-specific argument completion using _arguments.

    Parses tab-separated output from `poe _describe_task_args`:
        <options>\\t<type>\\t<help>\\t<choices>

    Handles:
    - Boolean flags: no value placeholder
    - Value options (string/integer/float): with value placeholder or choices
    - Positional args: file completion or choices
    - Multiple option forms: mutual exclusivity
    - Option filtering: skip options that have already been used
    """
    return f"""\
            # Complete task-specific arguments using _arguments
            local -a arg_specs
            local opts arg_type help_text choices val_compl

            [[ -z "$current_task" ]] && {{ _files; return; }}

            # Count existing options in command line for filtering
            local -A option_counts
            for ((i=2; i<${{#words[@]}}; i++)); do
                local w="${{words[i]}}"
                [[ "$w" == -* && "$w" != "--" ]] && (( option_counts[$w]++ ))
            done

            # Check cache for task args (hybrid: disk cache -> in-memory -> fetch)
            local effective_path="${{target_path:-$PWD}}"
            local args_cache_id="poe_args_${{current_task}}_${{effective_path//\\//_}}"
            local args_cache_key="${{effective_path}}|$current_task"
            local task_args_data
            local -a _poe_disk_args
            local cache_hit=0

            # Try caches first (if caching enabled)
            if (( _POE_CACHE_ENABLED )); then
                # Try disk cache first (conventional, works if use-cache enabled)
                # Note: _retrieve_cache sets arrays, so join with newlines to get string
                if ! {{ _cache_invalid $args_cache_id || ! _retrieve_cache $args_cache_id _poe_disk_args }} && (( ${{#_poe_disk_args[@]}} > 0 )); then
                    task_args_data="${{(pj:\\n:)_poe_disk_args}}"
                    cache_hit=1
                # Fall back to in-memory cache (with TTL check)
                elif [[ -v _poe_mem_args[$args_cache_key] ]] && (( (SECONDS - ${{_poe_mem_args_time[$args_cache_key]:-0}}) < _POE_CACHE_TTL )); then
                    task_args_data="${{_poe_mem_args[$args_cache_key]}}"
                    cache_hit=1
                fi
                # Check max cache hits (force refresh after N hits)
                if (( cache_hit )); then
                    (( _poe_cache_hits_args[$args_cache_key]++ ))
                    if (( _poe_cache_hits_args[$args_cache_key] >= _POE_CACHE_MAX_HITS )); then
                        cache_hit=0
                    fi
                fi
            fi

            # Fetch fresh if no cache hit
            if (( ! cache_hit )); then
                task_args_data="$({name} _describe_task_args "$current_task" $target_path 2>/dev/null)"
                # Store to caches (if caching enabled and there are args)
                if (( _POE_CACHE_ENABLED )) && [[ -n "$task_args_data" ]]; then
                    # Split string into array for disk cache (one line per element)
                    _poe_disk_args=("${{(f)task_args_data}}")
                    _store_cache $args_cache_id _poe_disk_args
                    _poe_mem_args[$args_cache_key]="$task_args_data"
                    _poe_mem_args_time[$args_cache_key]=$SECONDS
                    _poe_cache_hits_args[$args_cache_key]=0
                fi
            fi

            while IFS=$'\\t' read -r opts arg_type help_text choices; do
                [[ -z "$opts" ]] && continue

                # Convert "_" placeholder back to empty (zsh read skips consecutive tabs)
                [[ "$choices" == "_" ]] && choices=""

                # Skip options that have already been used (positional args have their own rules)
                # BUT: don't skip if we're completing the value for this option (prev word is the option)
                if [[ "$arg_type" != "positional" ]]; then
                    local prev_word="${{words[CURRENT-1]}}"
                    local -a opt_arr=(${{(s:,:)opts}})

                    # Check if we're completing value for this option
                    local completing_value=0
                    for opt in $opt_arr; do
                        [[ "$prev_word" == "$opt" ]] && completing_value=1
                    done

                    # Only filter if not completing value for this option
                    if (( ! completing_value )); then
                        local total_count=0
                        for opt in $opt_arr; do
                            (( total_count += ${{option_counts[$opt]:-0}} ))
                        done
                        # Skip if already used
                        (( total_count >= 1 )) && continue
                    fi
                fi

                # Build value completion spec: use choices if available
                if [[ -n "$choices" ]]; then
                    val_compl=":value:($choices)"
                else
                    val_compl=":value:()"
                fi

                if [[ "$opts" == *,* ]]; then
                    # Multiple option forms - split and add with mutual exclusivity
                    local -a opt_arr=(${{(s:,:)opts}})
                    local excl="(${{(j: :)opt_arr}})"

                    for opt in $opt_arr; do
                        case "$arg_type" in
                            boolean)
                                arg_specs+=("${{excl}}${{opt}}"'['"$help_text"']')
                                ;;
                            *)
                                arg_specs+=("${{excl}}${{opt}}"'['"$help_text"']'"$val_compl")
                                ;;
                        esac
                    done
                else
                    # Single option form
                    case "$arg_type" in
                        boolean)
                            arg_specs+=("$opts"'['"$help_text"']')
                            ;;
                        positional)
                            # Use choices if available, otherwise file completion
                            if [[ -n "$choices" ]]; then
                                if [[ -n "$help_text" ]]; then
                                    arg_specs+=(":$opts -- $help_text:($choices)")
                                else
                                    arg_specs+=(":$opts:($choices)")
                                fi
                            else
                                if [[ -n "$help_text" ]]; then
                                    arg_specs+=(":$opts -- $help_text:_files")
                                else
                                    arg_specs+=(":$opts:_files")
                                fi
                            fi
                            ;;
                        *)
                            arg_specs+=("$opts"'['"$help_text"']'"$val_compl")
                            ;;
                    esac
                fi
            done <<< "$task_args_data"

            # Fallback to _files if no args defined
            if (( ${{#arg_specs[@]}} == 0 )); then
                _files
            else
                _arguments -s "${{arg_specs[@]}}" '*:file:_files'
            fi
    """


def _get_fetch_tasks_func(name: str) -> str:
    """Generate the _poe_fetch_tasks zsh helper function.

    Encapsulates the full hybrid caching logic for task descriptions:
    disk cache -> in-memory cache -> fresh fetch (with hit counting and TTL).
    Sets the zsh `reply` array with task description lines.
    """
    return f"""\
# Fetch task descriptions with hybrid caching (disk -> in-memory -> fresh).
# Sets the reply array with task description lines.
# Usage: _poe_fetch_tasks "$effective_path" "$target_path"
_poe_fetch_tasks() {{
    local effective_path="$1"
    local target_path="$2"
    local cache_id="poe_tasks_${{effective_path//\\//_}}"
    local -a _poe_disk_tasks
    local cache_hit=0

    reply=()

    if (( _POE_CACHE_ENABLED )); then
        # Try disk cache first (conventional, works if use-cache enabled)
        if ! {{ _cache_invalid $cache_id || ! _retrieve_cache $cache_id _poe_disk_tasks }} && (( ${{#_poe_disk_tasks[@]}} > 0 )); then
            reply=($_poe_disk_tasks)
            cache_hit=1
        # Fall back to in-memory cache (with TTL check)
        elif [[ -v _poe_mem_tasks[$effective_path] ]] && (( (SECONDS - ${{_poe_mem_tasks_time[$effective_path]:-0}}) < _POE_CACHE_TTL )); then
            reply=(${{(f)_poe_mem_tasks[$effective_path]}})
            cache_hit=1
        fi
        # Force refresh after N cache hits
        if (( cache_hit )); then
            (( _poe_cache_hits_tasks[$effective_path]++ ))
            if (( _poe_cache_hits_tasks[$effective_path] >= _POE_CACHE_MAX_HITS )); then
                cache_hit=0
            fi
        fi
    fi

    if (( ! cache_hit )); then
        local result
        result="$({name} _zsh_describe_tasks $target_path 2>/dev/null)"
        # Fall back to _list_tasks if command failed or returned help text
        # (older poe versions don't have _zsh_describe_tasks)
        if [[ -z "$result" || "$result" == *"Poe the Poet"* || "$result" == *"Usage"* ]]; then
            local tasks
            tasks="$({name} _list_tasks $target_path 2>/dev/null)"
            result=""
            for task in ${{=tasks}}; do
                result+="$task:"$'\\n'
            done
        fi
        if (( _POE_CACHE_ENABLED )) && [[ -n "$result" ]]; then
            _poe_disk_tasks=(${{(f)result}})
            _store_cache $cache_id _poe_disk_tasks
            _poe_mem_tasks[$effective_path]="$result"
            _poe_mem_tasks_time[$effective_path]=$SECONDS
            _poe_cache_hits_tasks[$effective_path]=0
        fi
        reply=(${{(f)result}})
    fi
}}"""


def _format_global_options(
    options: "list[Action]",
    excl_groups: "list[set[Action]]",
) -> list[str]:
    """
    Format global CLI options for zsh _arguments.

    Returns a list of argument spec strings for _arguments -C.
    Handles mutual exclusivity and special cases (help, version).
    """

    def format_exclusions(excl_option_strings: set[str]) -> str:
        # Don't include $ALL_EXLC - regular options shouldn't exclude --help/--version
        # This allows `poe -C path --help` to work
        return f"({' '.join(sorted(excl_option_strings))})"

    args_lines = ["    _arguments -C"]

    for option in options:
        if option.help == "==SUPPRESS==":
            continue

        # help and version are mutually exclusive with each other, but can follow other options
        # (e.g., `poe -C path --help` should work)
        if option.dest == "help":
            # --help can optionally take a task name
            options_part = (
                option.option_strings[0]
                if len(option.option_strings) == 1
                else '"{' + ",".join(sorted(option.option_strings)) + '}"'
            )
            args_lines.append(
                f'"($ALL_EXLC){options_part}[{option.help}]::task:->help_task"'
            )
            continue

        if option.dest == "version":
            options_part = (
                option.option_strings[0]
                if len(option.option_strings) == 1
                else '"{' + ",".join(sorted(option.option_strings)) + '}"'
            )
            args_lines.append(f'"($ALL_EXLC){options_part}[{option.help}]"')
            continue

        # collect other options that are exclusive to this one
        excl_options: Iterable[Any] = next(
            (
                excl_group - {option}
                for excl_group in excl_groups
                if option in excl_group
            ),
            (),
        )
        # collect all option strings that are exclusive with this one
        excl_option_strings: set[str] = {
            option_string
            for excl_option in excl_options
            for option_string in excl_option.option_strings
        } | set(option.option_strings)

        if len(excl_option_strings) == 1:
            options_part = option.option_strings[0]
        elif len(option.option_strings) == 1:
            options_part = (
                format_exclusions(excl_option_strings) + option.option_strings[0]
            )
        else:
            options_part = (
                format_exclusions(excl_option_strings)
                + '"{'
                + ",".join(sorted(option.option_strings))
                + '}"'
            )

        # Check if option takes a value (nargs=0 means no value, like store_true)
        # Options with const but no nargs are also no-value (store_const)
        takes_value = option.nargs != 0 and not (
            option.const is not None and option.nargs is None and option.type is None
        )

        if takes_value:
            # Add value placeholder based on option type
            if option.dest == "project_root":
                args_lines.append(f'"{options_part}[{option.help}]:directory:_files"')
            elif option.dest == "executor":
                # Known executor types
                args_lines.append(
                    f'"{options_part}[{option.help}]'
                    ':executor:(auto poetry simple uv virtualenv)"'
                )
            elif option.dest == "executor_options":
                # -X/--executor-opt takes arbitrary key=value, no useful completion
                # but must have value placeholder so zsh knows it consumes a value
                args_lines.append(f'"{options_part}[{option.help}]:opt:()"')
            else:
                args_lines.append(f'"{options_part}[{option.help}]:value:()"')
        else:
            args_lines.append(f'"{options_part}[{option.help}]"')

    # State transitions for task and args completion
    args_lines.append('"1: :->task"')
    args_lines.append('"*::arg:->args"')

    return args_lines


def get_zsh_completion_script(name: str = "") -> str:
    """
    Generate a zsh completion script for poe.

    The script provides completion for:
    - Global CLI options (from argparse)
    - Task names with descriptions
    - Task-specific arguments (options and positionals)
    """
    from pathlib import Path

    from ..app import PoeThePoet

    name = name or "poe"

    # Build and interrogate the argument parser as the normal CLI would
    app = PoeThePoet(cwd=Path().resolve())
    parser = app.ui.build_parser()
    global_options = parser._action_groups[1]._group_actions
    excl_groups = [
        set(excl_group._group_actions)
        for excl_group in parser._mutually_exclusive_groups
    ]

    args_lines = _format_global_options(global_options, excl_groups)

    # Task state: load descriptions only when completing task names
    # Delegates to _poe_fetch_tasks for hybrid caching logic
    task_state_handler = """\
            # Don't show tasks if user is typing an option (starts with -)
            [[ ${words[CURRENT]} == -* ]] && return

            local effective_path="${target_path:-$PWD}"
            _poe_fetch_tasks "$effective_path" "$target_path"
            local -a task_descriptions=("${reply[@]}")
            _describe 'task' task_descriptions"""

    # help_task state: offer task names for --help [task]
    # Same caching as task state, without the option-prefix guard
    help_task_state_handler = """\
            local effective_path="${target_path:-$PWD}"
            _poe_fetch_tasks "$effective_path" "$target_path"
            local -a task_descriptions=("${reply[@]}")
            _describe 'task' task_descriptions"""

    # State handling logic
    # _arguments -C can set multiple space-separated states when ambiguous
    # e.g., "help_task task" when --help's optional value could also be first positional
    # We use pattern matching to check for each state as a word
    state_handling = f"""
    # Handle states (may be space-separated when ambiguous)
    # Check for each state as a word using " $state " pattern
    if [[ " $state " == *" help_task "* ]]; then
{help_task_state_handler}
    elif [[ " $state " == *" task "* ]]; then
{task_state_handler}
    elif [[ " $state " == *" args "* ]]; then
{_get_describe_task_args_completion(name)}
    fi
"""

    # Cache policy function: invalidate after 1 hour
    cache_policy_func = """\
# Set to 1 to enable caching, 0 to disable (useful for debugging)
_POE_CACHE_ENABLED=1

# TTL for in-memory cache in seconds (matches disk cache policy of 1 hour)
_POE_CACHE_TTL=3600

# Max cache hits before forcing a refresh (prevents serving stale data forever
# within a long-lived shell session, even when disk cache TTL hasn't expired)
_POE_CACHE_MAX_HITS=10

# Cache policy: invalidate after 1 hour
_poe_caching_policy() {
    local -a oldp
    oldp=( "$1"(Nmh+1) )  # Files modified more than 1 hour ago
    (( $#oldp ))
}
"""

    fetch_tasks_func = _get_fetch_tasks_func(name)

    return "\n".join(
        [
            f"#compdef {name}\n",
            cache_policy_func,
            fetch_tasks_func,
            "",
            f"function _{name} {{",
            "    local state",
            _TARGET_PATH_LOGIC,
            '    local ALL_EXLC=("-h" "--help" "--version")',
            "",
            " \\\n        ".join(args_lines),
            state_handling,
            "}",
            "",
            # Call the function when autoloaded (standard zsh pattern)
            f'_{name} "$@"',
        ]
    )
