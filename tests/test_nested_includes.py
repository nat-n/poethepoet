"""
Tests for nested/recursive includes feature.

Include files can themselves include other files, loaded depth-first.
Cycle detection, relative path resolution, and the recursive=false option
are also tested here.
"""

# -- Basic nesting --


def test_task_from_root(run_poe):
    result = run_poe("root_task", project="nested_includes")
    assert "Poe => poe_test_echo root" in result.capture
    assert result.stdout == "root\n"


def test_task_from_direct_include(run_poe):
    result = run_poe("a_task", project="nested_includes")
    assert "Poe => poe_test_echo a" in result.capture
    assert result.stdout == "a\n"


def test_task_from_second_level_include(run_poe):
    result = run_poe("b_task", project="nested_includes")
    assert "Poe => poe_test_echo b" in result.capture
    assert result.stdout == "b\n"


def test_task_from_third_level_include(run_poe):
    """
    deep_leaf.toml is three levels deep:
    root -> level_a -> subdir/sub_level -> deeper/deep_leaf
    """
    result = run_poe("deep_leaf_task", project="nested_includes")
    assert "Poe => poe_test_echo deep_leaf" in result.capture
    assert result.stdout == "deep_leaf\n"


# -- Task precedence --


def test_root_task_wins_over_included(run_poe):
    """override_task is defined in root, level_a, and level_b; root wins."""
    result = run_poe("override_task", project="nested_includes")
    assert result.stdout == "root_wins\n"
    assert result.stderr == ""


def test_dfs_task_ordering(run_poe):
    """Task listing follows DFS: level_a subtree before sibling_d subtree."""
    result = run_poe(project="nested_includes")
    capture = result.capture
    # a_task (from level_a) listed before d_task (from sibling_d)
    assert capture.index("a_task") < capture.index("d_task")
    # b_task (from level_b, child of level_a) listed before d_task
    assert capture.index("b_task") < capture.index("d_task")


# -- Env and task precedence across nesting levels --


def test_root_env_wins_over_nested(run_poe):
    """
    PRECEDENCE_ENV defined in root, level_a, and level_b.
    Root config is applied last so its value wins.
    """
    result = run_poe("check_precedence", project="nested_includes")
    words = result.stdout.split()
    # Root's value wins over level_a and level_b
    assert "PRECEDENCE=from_root" in words
    # Verify the losing partitions are actually loaded (not silently broken)
    result = run_poe("check_all_env", project="nested_includes")
    words = result.stdout.split()
    assert "A=from_a" in words
    assert "B=from_b" in words


def test_later_dfs_sibling_env_overwrites_earlier(run_poe):
    """
    SIBLING_PRECEDENCE_ENV defined in level_b (in level_a's subtree) and
    sibling_d (root's next include after level_a). DFS processes level_a's
    subtree first, so sibling_d is applied later and its value wins.
    """
    result = run_poe("check_precedence", project="nested_includes")
    words = result.stdout.split()
    assert "SIBLING=from_d" in words
    # Verify level_b is actually loaded (its unique env var works)
    result = run_poe("check_all_env", project="nested_includes")
    assert "B=from_b" in result.stdout.split()


def test_env_from_all_nesting_levels(run_poe):
    """Env vars from root, level_a, level_b, sibling_d all available globally."""
    result = run_poe("check_all_env", project="nested_includes")
    lines = result.stdout.strip().split()
    assert "ROOT=from_root" in lines
    assert "A=from_a" in lines
    assert "B=from_b" in lines
    assert "D=from_d" in lines
    assert result.stderr == ""


# -- Envfile in nested includes --


def test_envfile_with_poe_conf_dir_in_nested_include(run_poe):
    """
    deep_leaf.toml uses envfile = '${POE_CONF_DIR}/deep_leaf.env'
    to load config-relative envfile.
    """
    result = run_poe("deep_leaf_env_task", project="nested_includes")
    assert result.stdout == "DEEP_VAL=from_deep\n"
    assert result.stderr == ""


def test_bare_envfile_in_nested_include_resolves_from_project_root(run_poe):
    """
    level_b.toml (nested via level_a) uses envfile = 'root_level.env'
    which resolves from project root.
    """
    result = run_poe("b_root_envfile_task", project="nested_includes")
    assert result.stdout == "ROOT_LEVEL_VAR=from_root_level\n"
    assert result.stderr == ""


# -- Relative path resolution --


def test_nested_include_relative_to_parent(run_poe):
    """Nested include paths resolve relative to parent file, not project root.

    level_a includes subdir/sub_level.toml (relative to project root).
    sub_level.toml includes deeper/deep_leaf.toml (relative to subdir/).
    """
    result = run_poe("sub_task", project="nested_includes")
    assert result.stdout == "sub\n"
    result = run_poe("deep_leaf_task", project="nested_includes")
    assert result.stdout == "deep_leaf\n"


# -- ${POE_ROOT} in nested include --


def test_poe_root_in_nested_include(run_poe):
    """level_b uses ${POE_ROOT}/poe_root_ref.toml — resolves to project root."""
    result = run_poe("poe_root_task", project="nested_includes")
    assert result.stdout == "poe_root\n"
    assert result.stderr == ""


# -- cwd and POE_CONF_DIR --


def test_cwd_sets_poe_conf_dir(run_poe, is_windows):
    """
    cwd_tasks.toml included via level_a with cwd='cwd_dir'.
    POE_CONF_DIR reflects cwd_dir.
    """
    result = run_poe("cwd_confdir_task", project="nested_includes")
    assert result.code == 0
    separator = "\\" if is_windows else "/"
    assert result.stdout.strip().endswith(f"nested_includes_project{separator}cwd_dir")


def test_cwd_envfile_in_nested_include(run_poe):
    """
    Envfile 'cwd.env' in nested cwd_tasks.toml
    (included via level_a with cwd='cwd_dir') resolves relative to cwd.
    """
    result = run_poe("cwd_env_task", project="nested_includes")
    assert result.stdout == "CWD_VAR=from_cwd_dir\n"
    assert result.stderr == ""


# -- Cycle detection --


def test_direct_cycle_detected(run_poe, projects):
    """cycle_a includes cycle_b which includes cycle_a. Cycle is warned, not fatal."""
    result = run_poe(
        "-v",
        f"-C={projects['nested_includes/cycle_a']}",
        "cycle_a_task",
    )
    assert result.code == 0
    assert result.stdout == "cycle_a\n"
    assert "Cyclic include detected" in result.capture

    result = run_poe(
        f"-C={projects['nested_includes/cycle_a']}",
        "cycle_b_task",
    )
    assert result.code == 0
    assert result.stdout == "cycle_b\n"


def test_deep_cycle_detected(run_poe, projects):
    """
    deep_cycle -> chain_b -> chain_c -> deep_cycle/chain_b.
    Cycle is warned, not fatal.
    """
    deep_cycle_dir = str(projects["nested_includes/deep_cycle"].parent)
    result = run_poe(f"-C={deep_cycle_dir}", "deep_root_task")
    assert result.code == 0
    assert result.stdout == "deep_root\n"

    result = run_poe(f"-C={deep_cycle_dir}", "deep_b_task")
    assert result.code == 0
    assert result.stdout == "deep_b\n"

    result = run_poe(f"-C={deep_cycle_dir}", "deep_c_task")
    assert result.code == 0
    assert result.stdout == "deep_c\n"


# -- DAG dedup --


def test_shared_include_dag(run_poe):
    """shared.toml included by both level_b and sibling_d — no error, task available."""
    result = run_poe("shared_task", project="nested_includes")
    assert result.code == 0
    assert result.stdout == "shared\n"
    assert result.stderr == ""


def test_first_included_task_wins(run_poe):
    """
    dup_task defined in shared.toml and sibling_d.toml;
    shared.toml is included first (via level_b DFS).
    """
    result = run_poe("dup_task", project="nested_includes")
    assert result.code == 0
    assert result.stdout == "from_shared\n"


# -- Missing nested include --


def test_missing_nested_include_warns(run_poe):
    """
    missing_ref.toml includes a nonexistent file.
    Warning is issued, surviving_task works.
    """
    result = run_poe("surviving_task", project="nested_includes")
    assert result.code == 0
    assert result.stdout == "survived\n"
    assert "does_not_exist.toml" in result.capture


# -- tool.poe namespacing --


def test_tool_poe_namespace_in_nested_include(run_poe):
    """with_tool_poe.toml uses [tool.poe.tasks] namespacing in a nested include."""
    result = run_poe("tool_poe_task", project="nested_includes")
    assert result.stdout == "tool_poe_works\n"
    assert result.stderr == ""


# -- Task groups --


def test_groups_in_nested_includes(run_poe):
    """
    groups_nested.toml defines a group; groups_child.toml adds to it.
    Both tasks are merged under the same heading.
    """
    result = run_poe("compile_task", project="nested_includes")
    assert result.stdout == "compiling\n"

    result = run_poe("package_task", project="nested_includes")
    assert result.stdout == "packaging\n"

    result = run_poe("child_ungrouped", project="nested_includes")
    assert result.stdout == "child_ungrouped\n"

    # Verify both grouped tasks appear after the heading (merged into one group)
    result = run_poe(project="nested_includes")
    capture = result.capture
    heading_pos = capture.index("Build Tasks")
    assert capture.index("compile_task") > heading_pos
    assert capture.index("package_task") > heading_pos
    # Ungrouped task from child is listed before the group heading
    assert capture.index("child_ungrouped") < heading_pos


# -- recursive option --


def test_recursive_true_explicit(run_poe):
    """
    level_a includes level_b with explicit recursive=true.
    level_b's children (shared, poe_root_ref) are followed.
    """
    result = run_poe("shared_task", project="nested_includes")
    assert result.code == 0
    assert result.stdout == "shared\n"

    result = run_poe("poe_root_task", project="nested_includes")
    assert result.code == 0
    assert result.stdout == "poe_root\n"


def test_recursive_false_loads_direct_tasks(run_poe, projects):
    """recursive=false still loads the included file's own tasks."""
    result = run_poe(
        f"-C={projects['nested_includes/nonrecursive_parent']}",
        "nr_child_task",
    )
    assert result.code == 0
    assert result.stdout == "nr_child\n"


def test_recursive_false_blocks_grandchild(run_poe, projects):
    """recursive=false prevents the included file's own includes from being followed."""
    result = run_poe(
        f"-C={projects['nested_includes/nonrecursive_parent']}",
    )
    assert "nr_parent_task" in result.capture
    assert "nr_child_task" in result.capture
    assert "nr_grandchild_task" not in result.capture


def test_recursive_false_on_root_include(run_poe):
    """Root pyproject.toml includes nonrecursive_child.toml with recursive=false.
    nr_child_task is available but nr_grandchild_task is not."""
    result = run_poe(project="nested_includes")
    assert "nr_child_task" in result.capture
    assert "nr_grandchild_task" not in result.capture
