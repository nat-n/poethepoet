def test_nested_array_as_parallel_task(run_poe_subproc, esc_prefix):
    """
    Test that a nested array in a sequence is interpreted as a parallel task.

    The composite_task in sequences_project has a nested array that should now
    be interpreted as a parallel task.
    """
    result = run_poe_subproc("composite_task", project="sequences")

    # The output should contain the commands for part1 and _part2 in parallel,
    # followed by the command for the third task
    assert "Poe => poe_test_echo Hello" in result.capture
    assert "Poe => poe_test_echo 'World!'" in result.capture
    assert "Poe => poe_test_echo ':)!'" in result.capture

    # The stdout should contain the output from all tasks
    assert "Hello" in result.stdout
    assert "World!" in result.stdout
    assert ":)!" in result.stdout

    # There should be no errors
    assert result.stderr == ""


def test_mixed_sequence_task(run_poe_subproc):
    """
    This should run mypy and pylint in parallel, then pytest after they complete.
    """

    # Create a simple task that just echoes its name to simulate a real command
    result = run_poe_subproc("test_mixed", project="sequences")

    # Check that the tasks ran in the expected order (parallel tasks first, then
    # sequential)
    # To ensure parallel tasks start before sequential, check the indices of their
    # "Running" messages.
    mypy_start_index = result.stdout.find("Running mypy")
    pylint_start_index = result.stdout.find("Running pylint")
    pytest_start_index = result.stdout.find("Running pytest")

    # Ensure all start messages are found
    assert mypy_start_index != -1
    assert pylint_start_index != -1
    assert pytest_start_index != -1

    # Ensure that both mypy and pylint "Running" messages appear before pytest's
    # "Running" message.
    # This implies they started before pytest.
    assert mypy_start_index < pytest_start_index
    assert pylint_start_index < pytest_start_index
