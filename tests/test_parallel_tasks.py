# ruff: noqa: E501
from collections.abc import Sequence

import pytest

BUFFER_LIMIT_OVERRIDE = 64
BUFFER_LIMIT_OVERRIDE_ENV = {"POE_BUFFERED_STDOUT_LIMIT": str(BUFFER_LIMIT_OVERRIDE)}


def format_parallel_prefix(task_name: str, prefix_max: int = 16) -> str:
    if len(task_name) > prefix_max:
        task_name = task_name[: prefix_max - 1] + "…"
    return f"{task_name} | "


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
def test_parallel_task_with_redirected_outputs(run_poe, tests_temp_dir):
    result = run_poe("parallel_with_stdout_capture", project="parallel")

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
def test_parallel_task_buffered_output_mode(
    run_poe_subproc, temp_pyproject, delay_factor
):
    slow_delay = 80 * delay_factor
    fast_delay = 20 * delay_factor
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.buffered]
            parallel = [
              {{ shell = "poe_test_echo slow-1 && poe_test_delayed_echo {slow_delay} slow-2" }},
              {{ shell = "poe_test_delayed_echo {fast_delay} fast-1 && poe_test_delayed_echo {fast_delay} fast-2" }},
            ]
            output_mode = "buffer"
        """
    )

    result = run_poe_subproc("buffered", cwd=project_path)

    assert result.stdout == (
        "buffered[1] | fast-1\n"
        "buffered[1] | fast-2\n"
        "buffered[0] | slow-1\n"
        "buffered[0] | slow-2\n"
    )


def test_parallel_task_buffered_output_flushes_on_failure(
    run_poe_subproc, temp_pyproject
):
    # A non-zero exit must not swallow buffered output. Here the flush is reached
    # via the failing subtask's own stdout EOF (the async-for ends, then the
    # finally flushes) — distinct from the cancellation test, where a sibling's
    # buffer is flushed mid-stream as the group is torn down.
    project_path = temp_pyproject(
        """
            [tool.poe.tasks.buffered_failure]
            parallel = [
              { shell = "import sys; print('before-fail'); sys.exit(3)", interpreter = "python" },
            ]
            output_mode = "buffer"
        """
    )

    result = run_poe_subproc("buffered_failure", cwd=project_path)

    assert (
        result.stdout == f"{format_parallel_prefix('buffered_failure[0]')}before-fail\n"
    )
    assert result.capture_lines == [
        "Poe => import sys; print('before-fail'); sys.exit(3)",
        "Warning: Parallel subtask 'buffered_failure[0]' failed with non-zero exit status",
        "Error: Parallel task 'buffered_failure' aborted after failed subtask 'buffered_failure[0]'",
    ]
    assert result.code == 1


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_task_buffered_output_flushes_on_cancellation(
    run_poe_subproc, temp_pyproject, delay_factor
):
    # One subtask buffers a line then blocks; a sibling fails, aborting the group
    # and cancelling the blocked subtask. Its already-buffered output must still
    # be flushed (the "or is cancelled" promise), rather than being swallowed.
    abort_delay = 0.2 * delay_factor
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.buffered_cancelled]
            parallel = [
              {{ shell = "import time; print('cancelled-output', flush=True); time.sleep(10)", interpreter = "python" }},
              {{ shell = "import time, sys; time.sleep({abort_delay}); sys.exit(7)", interpreter = "python" }},
            ]
            output_mode = "buffer"
        """
    )

    result = run_poe_subproc("buffered_cancelled", cwd=project_path, timeout=15)

    # The cancelled subtask's buffered line is flushed; the failing sibling
    # produces no stdout, so this is the entire output.
    assert result.stdout == (
        f"{format_parallel_prefix('buffered_cancelled[0]')}cancelled-output\n"
    )
    assert result.code == 1
    # The abort is attributed to the failing sibling [1], not the cancelled [0].
    assert (
        "Warning: Parallel subtask 'buffered_cancelled[1]' "
        "failed with non-zero exit status" in result.capture_lines
    )
    assert (
        "Error: Parallel task 'buffered_cancelled' aborted after failed subtask "
        "'buffered_cancelled[1]'" in result.capture_lines
    )


@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_parallel_task_buffered_output_flushes_large_buffers_by_line(
    run_poe_subproc_handle, temp_pyproject
):
    line_size = 40
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.buffered_large]
            parallel = [
              {{ shell = "import time; print('A' * {line_size}, flush=True); time.sleep(0.2); print('B' * {line_size}, flush=True); time.sleep(1.0); print('C' * {line_size}, flush=True)", interpreter = "python" }},
            ]
            output_mode = "buffer"
        """
    )

    expected_prefix = format_parallel_prefix("buffered_large[0]")
    first_output_line = f"{expected_prefix}{'A' * line_size}\n"
    expected_output = first_output_line + (
        f"{expected_prefix}{'B' * line_size}\n" f"{expected_prefix}{'C' * line_size}\n"
    )

    handle = run_poe_subproc_handle(
        "buffered_large",
        cwd=str(project_path),
        env=BUFFER_LIMIT_OVERRIDE_ENV,
    )
    stdout = handle.process.stdout
    assert stdout is not None

    # The first line is flushed once the buffer crosses the limit, before the
    # task finishes — so the process is still running when it arrives.
    first_line = stdout.readline().decode(errors="ignore").replace("\r\n", "\n")
    assert first_line == first_output_line
    assert handle.process.poll() is None

    # Drain the remainder from the same buffered reader. Mixing readline() with
    # result()/communicate() drops lines that readline already buffered when
    # several are flushed in a single write.
    remaining = stdout.read().decode(errors="ignore").replace("\r\n", "\n")
    handle.process.wait(timeout=10)
    assert first_line + remaining == expected_output


def test_parallel_task_buffered_long_complete_line_emitted_whole(
    run_poe_subproc, temp_pyproject
):
    # A complete line is emitted whole with a single prefix even when longer than
    # the buffer limit: it is already fully buffered, so wrapping it would save no
    # memory. Only an incomplete (newline-less) line at the limit is wrapped.
    # line_size is kept well under the read size so the line arrives in a single
    # read and its newline is seen before the limit is reached.
    line_size = 128
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.buffered_huge_line]
            parallel = [
              {{ shell = "print('X' * {line_size}, flush=True)", interpreter = "python" }},
            ]
            output_mode = "buffer"
        """
    )

    result = run_poe_subproc(
        "buffered_huge_line",
        cwd=project_path,
        env=BUFFER_LIMIT_OVERRIDE_ENV,
    )

    prefix = format_parallel_prefix("buffered_huge_line[0]")
    assert result.stdout == f"{prefix}{'X' * line_size}\n"


def test_parallel_task_streaming_long_complete_line_emitted_whole(
    run_poe_subproc, temp_pyproject
):
    # Same in streaming mode: a complete line longer than the limit is emitted
    # whole, not chopped into limit-sized segments. line_size is kept well under
    # the read size so the line arrives in a single read and its newline is seen
    # before the limit is reached.
    line_size = 200
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.streamed_huge_line]
            parallel = [
              {{ shell = "print('X' * {line_size}, flush=True)", interpreter = "python" }},
            ]
        """
    )
    prefix = format_parallel_prefix("streamed_huge_line[0]")
    expected = f"{prefix}{'X' * line_size}\n"

    result = run_poe_subproc(
        "streamed_huge_line",
        cwd=project_path,
        env=BUFFER_LIMIT_OVERRIDE_ENV,
    )
    assert result.stdout == expected

    # A line emitted whole was not wrapped, so even in verbose mode it must not
    # produce a wrap warning.
    verbose = run_poe_subproc(
        "-v", "streamed_huge_line", cwd=project_path, env=BUFFER_LIMIT_OVERRIDE_ENV
    )
    assert verbose.stdout == expected
    assert "was wrapped" not in verbose.capture


def test_parallel_task_oversized_line_does_not_corrupt_sibling(
    run_poe_subproc, temp_pyproject
):
    # Wrapping a >limit line must never weld a sibling's prefixed line onto a
    # partial flush. Task A builds a >limit line in spaced pieces (forcing many
    # mid-line flushes); task B prints many marker lines throughout, so under the
    # bug at least one is near-certain to land mid-flush and corrupt. No flaky
    # rerun here: a correctness guard must fail deterministically under the bug.
    marker_count = 12
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.interleave]
            parallel = [
              {{ shell = "import sys,time; [ (sys.stdout.write('A'*20), sys.stdout.flush(), time.sleep(0.08)) for _ in range(15) ]; sys.stdout.write(chr(10))", interpreter = "python" }},
              {{ shell = "import time; [ (print(f'B{{i}}', flush=True), time.sleep(0.1)) for i in range({marker_count}) ]", interpreter = "python" }},
            ]
        """
    )

    result = run_poe_subproc(
        "interleave", cwd=project_path, env=BUFFER_LIMIT_OVERRIDE_ENV, timeout=15
    )

    lines = result.stdout.splitlines()
    prefix_a = format_parallel_prefix("interleave[0]")
    prefix_b = format_parallel_prefix("interleave[1]")
    # Every marker line survives intact on its own line, never welded into A's.
    for index in range(marker_count):
        assert f"{prefix_b}B{index}" in lines
    # Every line begins with a recognized prefix — a prefix appearing mid-line
    # (or a line with none) is the signature of the corruption.
    assert all(line.startswith((prefix_a, prefix_b)) for line in lines)


def test_parallel_task_oversized_line_warns_only_when_verbose(
    run_poe_subproc, temp_pyproject
):
    # A wrapped line emits a single warning regardless of how many segments it is
    # split into, and only in verbose mode. The line has no trailing newline so
    # it is forced to wrap (a complete line would be emitted whole).
    line_size = 200
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.warned]
            parallel = [
              {{ shell = "import sys; sys.stdout.write('X' * {line_size}); sys.stdout.flush()", interpreter = "python" }},
            ]
        """
    )
    warning = (
        "Warning: Parallel subtask 'warned[0]' emitted a line exceeding the "
        f"{BUFFER_LIMIT_OVERRIDE}B output buffer limit; it was wrapped"
    )

    quiet = run_poe_subproc("warned", cwd=project_path, env=BUFFER_LIMIT_OVERRIDE_ENV)
    assert warning not in quiet.capture_lines
    # The over-limit line is flushed whole (all the data accumulated so far), not
    # chopped to a limit-sized slice, with a single synthetic terminating newline.
    assert quiet.stdout == f"{format_parallel_prefix('warned[0]')}{'X' * line_size}\n"

    verbose = run_poe_subproc(
        "-v", "warned", cwd=project_path, env=BUFFER_LIMIT_OVERRIDE_ENV
    )
    assert verbose.capture_lines.count(warning) == 1


def test_parallel_task_buffered_output_without_trailing_newline(
    run_poe_subproc, temp_pyproject
):
    # A final line shorter than the limit is forwarded as-is via the EOF tail,
    # with no trailing newline added (only an over-limit line is force-wrapped).
    line_size = 50
    project_path = temp_pyproject(
        f"""
            [tool.poe.tasks.buffered_no_newline]
            parallel = [
              {{ shell = "import sys; sys.stdout.write('Y' * {line_size}); sys.stdout.flush()", interpreter = "python" }},
            ]
            output_mode = "buffer"
        """
    )

    result = run_poe_subproc(
        "buffered_no_newline",
        cwd=project_path,
        env=BUFFER_LIMIT_OVERRIDE_ENV,
    )

    prefix = format_parallel_prefix("buffered_no_newline[0]")
    assert result.stdout == f"{prefix}{'Y' * line_size}"


def test_parallel_task_buffered_output_with_prefix_disabled(
    run_poe_subproc, temp_pyproject
):
    # With prefix = false the buffered lines are emitted verbatim, with no
    # prefix prepended to any line of the flushed block.
    project_path = temp_pyproject(
        """
            [tool.poe.tasks.buffered_no_prefix]
            parallel = [
              { shell = "print('line-1'); print('line-2')", interpreter = "python" },
            ]
            output_mode = "buffer"
            prefix = false
        """
    )

    result = run_poe_subproc("buffered_no_prefix", cwd=project_path)

    assert result.stdout == "line-1\nline-2\n"


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

        slow_delay = 5 * 100 * delay_factor
        fail_delay = 2 * 100 * delay_factor

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


def test_parallel_fail_all(run_poe_subproc, generate_pyproject, delay_factor):
    slow_delay = 5 * 100 * delay_factor
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
    assert (
        sequences_are_similar(
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
        )
        or sequences_are_similar(
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
        or sequences_are_similar(
            result.capture_lines,
            [
                f"Poe => poe_test_delayed_echo {slow_delay} 'Eventual success!'",
                "Poe => echo 'Great success!'",
                "Poe => echo 'failing fast with error'; exit 1;",
                "Poe => echo 'Great success!'",
                "Poe => echo 'Great success!'",
                "Warning: Parallel subtask 'fast_fail' failed with non-zero exit status",
                "Error: Parallel task 'lvl1_para' aborted after failed subtask 'fast_fail'",
                "Poe => echo 'failing fast with error'; exit 1;",
            ],
        )
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

    result = run_poe_subproc("lvl2_seq", cwd=project_path)

    # Sporadically there are warnings like:
    #    Warning: Exception while closing stdin for 25569: [Errno 32] Broken pipe
    # These need to be filtered out, as it is timing dependent if they occur or not.
    lvl2_seq_capture_lines = filter_capture_lines(
        result.capture_lines, "Warning: Exception while closing stdin"
    )
    assert sequences_are_similar(
        lvl2_seq_capture_lines,
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
        lvl2_seq_capture_lines,
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

    # fast_success from lvl1_seq (running as a parallel subtask) may arrive before
    # or after fast_fail depending on timing, so accept 2 or 3 fast_success lines.
    # slow_success may also complete before fast_fail on slower systems.
    assert (
        result.stdout.startswith(
            "Great success!\n"
            "fast_success | Great success!\n"
            "fast_success | Great success!\n"
            "fast_fail | failing fast with error\n"
        )
        or result.stdout.startswith(
            "Great success!\n"
            "fast_success | Great success!\n"
            "fast_success | Great success!\n"
            "fast_success | Great success!\n"
            "fast_fail | failing fast with error\n"
        )
        or result.stdout.startswith(
            "Great success!\n"
            "fast_success | Great success!\n"
            "fast_success | Great success!\n"
            "fast_success | Great success!\n"
            "slow_success | Eventual success!\n"
            "fast_fail | failing fast with error\n"
        )
    )
    assert result.code == 1

    result = run_poe_subproc("lvl2_para", cwd=project_path)
    lvl2_para_capture_lines = filter_capture_lines(
        result.capture_lines, "Warning: Exception while closing stdin"
    )
    assert sequences_are_similar(
        lvl2_para_capture_lines,
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
        lvl2_para_capture_lines,
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
    slow_delay = 5 * 100 * delay_factor
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
    slow_delay = 5 * 100 * delay_factor
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


def test_parallel_bool_flag(run_poe):
    """Parallel task: both cmd and expr subtasks see boolean args from parent"""
    result = run_poe("bool_parallel", "--flag", project="parallel")
    assert "cmd:True:True" in result.stdout
    assert "{'flag': True, 'val': True}" in result.stdout


def test_parallel_bool_defaults(run_poe):
    """Parallel task: False boolean arg is unset in cmd, typed False in expr"""
    result = run_poe("bool_parallel", project="parallel")
    assert "cmd:unset:True" in result.stdout
    assert "{'flag': False, 'val': True}" in result.stdout


def test_parallel_bool_negate(run_poe):
    """Parallel task: negating true-default boolean produces unset/False"""
    result = run_poe("bool_parallel", "--val", project="parallel")
    assert "cmd:unset:unset" in result.stdout
    assert "{'flag': False, 'val': False}" in result.stdout


def test_parallel_task_forwards_extra_args_via_poe_extra_args(run_poe):
    """Extra args passed to a parallel task are forwarded to subtasks via POE_EXTRA_ARGS"""
    result = run_poe("extra-args-parallel", "hello", "world", project="parallel")
    assert "extra: hello world" in result.stdout
    assert "Let it be" in result.stdout
    assert result.stderr == ""


def test_parallel_task_forwards_extra_args_with_trailing_args(run_poe):
    """$POE_EXTRA_ARGS in a parallel subtask can have args both before and after"""
    result = run_poe(
        "extra-args-parallel-trailing", "hello", "world", project="parallel"
    )
    assert "extra: before hello world after" in result.stdout
    assert result.stderr == ""


def filter_capture_lines(capture_lines: list[str], *prefixes: str) -> list[str]:
    return [
        line for line in capture_lines if not any(line.startswith(p) for p in prefixes)
    ]


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
