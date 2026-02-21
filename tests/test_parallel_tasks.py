# ruff: noqa: E501
from collections.abc import Sequence

import pytest


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_task_parallelism(run_poe_subproc, delay_factor):
    base = 50 * delay_factor
    d0, d1, d2, d3, d4 = 0, base, 2 * base, 3 * base, 4 * base
    result = run_poe_subproc(
        "--ansi",
        "sleep_sort",
        str(d0),
        str(d1),
        str(d2),
        str(d3),
        str(d4),
        project="parallel",
    )

    assert result.capture_lines == [
        f"\x1b[37mPoe =>\x1b[0m \x1b[94mpoe_test_delayed_echo {d3} {d3}\x1b[0m",
        f"\x1b[37mPoe =>\x1b[0m \x1b[94mpoe_test_delayed_echo {d0} {d0}\x1b[0m",
        f"\x1b[37mPoe =>\x1b[0m \x1b[94mpoe_test_delayed_echo {d4} {d4}\x1b[0m",
        f"\x1b[37mPoe =>\x1b[0m \x1b[94mpoe_test_delayed_echo {d2} {d2}\x1b[0m",
        f"\x1b[37mPoe =>\x1b[0m \x1b[94mpoe_test_delayed_echo {d1} {d1}\x1b[0m",
    ]
    assert result.stdout == (
        f"\x1b[32msleep_sort[1]\x1b[0m | {d0}\n"
        f"\x1b[35msleep_sort[4]\x1b[0m | {d1}\n"
        f"\x1b[34msleep_sort[3]\x1b[0m | {d2}\n"
        f"\x1b[31msleep_sort[0]\x1b[0m | {d3}\n"
        f"\x1b[33msleep_sort[2]\x1b[0m | {d4}\n"
    )


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_task_with_redirected_outputs(run_poe_subproc, tests_temp_dir):
    result = run_poe_subproc("parallel_with_stdout_capture", project="parallel")

    assert result.capture_lines == [
        "Poe => poe_test_echo '1 going to stdout 1'",
        "Poe <= poe_test_echo '2 going to file'",
        "Poe <= poe_test_echo '3 going to the void'",
        "Poe => poe_test_echo '4 going to stdout 4'",
    ]
    assert result.stdout == (
        "parallel_with_s… | 1 going to stdout 1\n"
        "parallel_with_s… | 4 going to stdout 4\n"
    )
    with tests_temp_dir.joinpath("captured2.txt").open("r") as f:
        assert f.read() == "2 going to file\n"


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_sequence_in_parallel_task(run_poe_subproc, delay_factor):
    base = 250 * delay_factor
    para_delay = 2 * base
    seq_delay = base
    result = run_poe_subproc(
        "parallel_of_sequences", str(para_delay), str(seq_delay), project="parallel"
    )

    assert result.capture_lines == [
        f"Poe => poe_test_delayed_echo {para_delay} para1",
        f"Poe => poe_test_delayed_echo {seq_delay} seq1",
        "Poe => poe_test_echo seq2",
    ]
    assert result.stdout == (
        "parallel_of_seq… | seq1\n"
        "parallel_of_seq… | seq2\n"
        "parallel_of_seq… | para1\n"
    )


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_in_sequence_task(run_poe_subproc, delay_factor):
    base = 50 * delay_factor
    seq_delay = 2 * base
    para_delay = base
    result = run_poe_subproc(
        "sequence_of_parallels", str(seq_delay), str(para_delay), project="parallel"
    )

    assert result.capture_lines == [
        f"Poe => poe_test_delayed_echo {seq_delay} seq1",
        f"Poe => poe_test_delayed_echo {para_delay} para1",
        "Poe => poe_test_echo para2",
    ]
    assert result.stdout == (
        "seq1\nsequence_of_par… | para2\nsequence_of_par… | para1\n"
    )


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_customize_parallel_task_prefix(run_poe_subproc):
    result = run_poe_subproc(
        "--ansi", "custom_prefix_task", project="parallel", timeout=10
    )
    assert set(result.output_lines) == {
        "\x1b[31m[0 : custom_prefix_task[0]]\x1b[0m I'm Mr. Meeseeks! Look at me!",
        "\x1b[32m[1 : custom_prefix_task[1]]\x1b[0m I'm Mr. Meeseeks! Look at me!",
        "\x1b[33m[2 : custom_prefix_task[2]]\x1b[0m I'm Mr. Meeseeks! Look at me!",
        "\x1b[34m[3 : custom_prefix_task[3]]\x1b[0m I'm Mr. Meeseeks! Look at me!",
        "\x1b[35m[4 : custom_prefix_task[4]]\x1b[0m I'm Mr. Meeseeks! Look at me!",
        "\x1b[36m[5 : custom_prefix_task[5]]\x1b[0m I'm Mr. Meeseeks! Look at me!",
        "\x1b[31m[6 : custom_prefix_task[6]]\x1b[0m I'm Mr. Meeseeks! Look at me!",
    }


@pytest.fixture
def generate_pyproject(temp_pyproject):
    def generator(
        delay_factor=1,
        seq1_ignore_fail=False,
        seq2_ignore_fail=False,
        para1_ignore_fail=False,
        para2_ignore_fail=False,
    ):
        def fmt_ignore_fail(value):
            if value is True:
                return "ignore_fail = true"
            elif isinstance(value, str):
                return f'ignore_fail = "{value}"'
            else:
                return ""

        slow_delay = 5 * 50 * delay_factor
        fail_delay = 2 * 50 * delay_factor

        project_tmpl = f"""
            [tool.poe.tasks]
            fast_success = "echo 'Great success!'"
            slow_success = "poe_test_delayed_echo {slow_delay} 'Eventual success!'"
            slow_fail = "poe_test_fail {fail_delay} 22"
            fast_fail.shell = "echo 'failing fast with error'; exit 1;"

            [tool.poe.tasks.lvl1_seq]
            help = "A sequence including a failing task"
            sequence = ["fast_success", "fast_fail", "fast_success"]
            {fmt_ignore_fail(seq1_ignore_fail)}

            [tool.poe.tasks.lvl1_para]
            help = "A parallel including a failing task"
            parallel = [
                "slow_success", "fast_success", "fast_fail", "fast_success", "lvl1_seq"
            ]
            {fmt_ignore_fail(para1_ignore_fail)}

            [tool.poe.tasks.lvl2_seq]
            help = "A sequence including a failing parallel task"
            sequence = ["fast_success", "lvl1_para", "fast_success"]
            {fmt_ignore_fail(seq2_ignore_fail)}

            [tool.poe.tasks.lvl2_para]
            parallel = ["slow_success", "lvl2_seq", "fast_success"]
            {fmt_ignore_fail(para2_ignore_fail)}
        """

        return temp_pyproject(project_tmpl)

    return generator


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_fail_all(run_poe_subproc, generate_pyproject, delay_factor):
    slow_delay = 5 * 50 * delay_factor
    project_path = generate_pyproject(delay_factor=delay_factor)

    result = run_poe_subproc("lvl1_seq", cwd=project_path)
    assert result.capture == (
        "Poe => echo 'Great success!'\n"
        "Poe => echo 'failing fast with error'; exit 1;\n"
        "Error: Sequence aborted after failed subtask 'fast_fail'\n"
    )
    assert result.stdout == "Great success!\nfailing fast with error\n"
    assert result.code == 1

    result = run_poe_subproc("lvl1_para", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        [
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Error: Parallel task 'lvl1_para' aborted after failed subtask 'fast_fail'",
        ],
    ) or sequences_are_similar(
        result.capture_lines,
        [
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Error: Parallel task 'lvl1_para' aborted after failed subtask 'fast_fail'",
        ],
    )
    assert set(result.output_lines) == {
        "fast_success | Great success!",
        "fast_fail | failing fast with error",
    }
    assert result.code == 1

    result = run_poe_subproc("lvl2_seq", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",  # not always reached
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Error: Sequence aborted after failed subtask 'lvl1_para'",
            "     | From: ExecutionError(\"Parallel task 'lvl1_para' aborted after failed subtask 'fast_fail'\")",
        ),
    ) or sequences_are_similar(
        result.capture_lines,
        (
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Error: Sequence aborted after failed subtask 'lvl1_para'",
            "     | From: ExecutionError(\"Parallel task 'lvl1_para' aborted after failed subtask 'fast_fail'\")",
        ),
    )

    assert result.stdout.startswith(
        "Great success!\n"
        "fast_success | Great success!\n"
        "fast_success | Great success!\n"
        "fast_fail | failing fast with error\n"
        # "fast_success | Great success!\n" # fast_success from lvl1_seq might get there
    )
    assert result.code == 1

    result = run_poe_subproc("lvl2_para", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",  # sometimes too late
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Warning: Parallel subtask 'lvl2_seq' failed with exception: Sequence aborted after failed subtask 'lvl1_para'",
            "Error: Parallel task 'lvl2_para' aborted after failed subtask 'lvl2_seq'",
        ),
    ) or sequences_are_similar(
        result.capture_lines,
        (
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Warning: Parallel subtask 'lvl2_seq' failed with exception: Sequence aborted after failed subtask 'lvl1_para'",
            "Error: Parallel task 'lvl2_para' aborted after failed subtask 'lvl2_seq'",
        ),
    )

    assert set(result.output_lines) in (
        {
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
        },
        {  # Sometimes the task takes longer to quit and we get more output
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "slow_success | Eventual success!",
        },
    )
    assert result.code == 1


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_ignore_failures(run_poe_subproc, generate_pyproject, delay_factor):
    slow_delay = 5 * 50 * delay_factor
    project_path = generate_pyproject(
        delay_factor=delay_factor,
        seq1_ignore_fail=True,
        seq2_ignore_fail=True,
        para1_ignore_fail=True,
        para2_ignore_fail=True,
    )

    result = run_poe_subproc("lvl1_seq", cwd=project_path)
    assert result.capture == (
        "Poe => echo 'Great success!'\n"
        "Poe => echo 'failing fast with error'; exit 1;\n"
        "Poe => echo 'Great success!'\n"
    )
    assert result.stdout == (
        "Great success!\nfailing fast with error\nGreat success!\n"
    )
    assert result.code == 0

    result = run_poe_subproc("lvl1_para", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Poe => echo 'Great success!'",
        ),
    )

    assert sequences_are_similar(
        result.output_lines,
        (
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "slow_success | Eventual success!",
        ),
    )
    assert result.code == 0

    result = run_poe_subproc("lvl2_seq", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
        ),
    )
    assert sequences_are_similar(
        result.output_lines,
        (
            "Great success!",
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "slow_success | Eventual success!",
            "Great success!",
        ),
    )
    assert result.code == 0

    result = run_poe_subproc("lvl2_para", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
        ),
    )

    assert sequences_are_similar(
        result.output_lines,
        (
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "slow_success | Eventual success!",
            "slow_success | Eventual success!",
            "fast_success | Great success!",
        ),
    )
    assert result.code == 0


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_ignore_but_propagate_failures(
    run_poe_subproc, generate_pyproject, delay_factor
):
    slow_delay = 5 * 50 * delay_factor
    project_path = generate_pyproject(
        delay_factor=delay_factor,
        seq1_ignore_fail=True,
        seq2_ignore_fail=True,
        para1_ignore_fail="return_non_zero",
        para2_ignore_fail=True,
    )

    result = run_poe_subproc("lvl1_para", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Poe => echo 'Great success!'",
            "Error: Subtask 'fast_fail' returned non-zero exit status",
        ),
    )

    assert sequences_are_similar(
        result.output_lines,
        (
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "slow_success | Eventual success!",
        ),
    )
    assert result.code == 1

    result = run_poe_subproc("lvl2_seq", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Poe => echo 'Great success!'",
            "Warning: Subtask 'fast_fail' returned non-zero exit status",
            "Poe => echo 'Great success!'",
        ),
    )
    assert sequences_are_similar(
        result.output_lines,
        (
            "Great success!",
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "slow_success | Eventual success!",
            "Great success!",
        ),
    )
    assert result.code == 0

    result = run_poe_subproc("lvl2_para", cwd=project_path)
    assert sequences_are_similar(
        result.capture_lines,
        (
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Poe => echo 'Great success!'",
            "Poe => echo 'Great success!'",
            "Poe => echo 'failing fast with error'; exit 1;",
            "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
            "Poe => echo 'Great success!'",
            "Warning: Subtask 'fast_fail' returned non-zero exit status",
            "Poe => echo 'Great success!'",
        ),
    )

    assert sequences_are_similar(
        result.output_lines,
        (
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "fast_fail | failing fast with error",
            "fast_success | Great success!",
            "slow_success | Eventual success!",
            "slow_success | Eventual success!",
            "fast_success | Great success!",
        ),
    )
    assert result.code == 0


def sequences_are_similar(seq1: Sequence, seq2: Sequence, distance: int = 1):
    """
    Check if two sequences have the same items in almost the same order.
    The distance param determines how far removed equal items can be to be considered
    similar.
    """
    if len(seq1) != len(seq2):
        return False

    null = object()
    index = 0
    compare = list(seq2)
    while index < len(seq1):
        for comp_index in range(
            max(0, index - distance), min(len(seq1), index + distance + 1)
        ):
            if seq1[index] == compare[comp_index]:
                compare[comp_index] = null
                index += 1
                break
        else:
            return False
    return True
