def test_script_task(run_poe_subproc, projects, esc_prefix):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc(
        "greet", "nat,", r"welcome to " + esc_prefix + "${POE_ROOT}"
    )
    assert result.capture == f"Poe => greet nat, welcome to {projects['example']}\n"
    assert result.stdout == f"hello nat, welcome to {projects['example']}\n"
    assert result.stderr == ""


def test_script_task_with_hard_coded_args(run_poe_subproc, projects, esc_prefix):
    # The $ has to be escaped or it'll be evaluated by the outer shell and poe will
    # never see it
    result = run_poe_subproc(
        "greet-shouty", "nat,", r"welcome to " + esc_prefix + "${POE_ROOT}"
    )
    assert (
        result.capture == f"Poe => greet-shouty nat, welcome to {projects['example']}\n"
    )
    assert result.stdout == f"hello nat, welcome to {projects['example']}\n".upper()
    assert result.stderr == ""
