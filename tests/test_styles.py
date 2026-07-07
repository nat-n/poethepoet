"""
Unit tests for ``poethepoet.styles`` — the palette of StyleCode callables that
poe uses to apply ANSI SGR codes to its own output, replacing the former
pastel-based tag system.
"""

import io

from poethepoet.io import PoeIO
from poethepoet.styles import ANSI_RESET, Style, StyleCode


def test_style_code_wraps_text_in_sgr_codes() -> None:
    assert StyleCode(Style(), 36)("hello") == "\x1b[36mhello\x1b[0m"


def test_style_code_joins_multiple_codes() -> None:
    assert StyleCode(Style(), 91, 1)("oops") == "\x1b[91;1moops\x1b[0m"


def test_style_code_stringifies_non_string_input() -> None:
    assert StyleCode(Style(), 36)(42) == "\x1b[36m42\x1b[0m"


def test_style_code_of_disabled_palette_returns_plain_text() -> None:
    style_code = StyleCode(Style(ansi_enabled=False), 36)
    assert style_code("hello") == "hello"
    assert style_code(42) == "42"


def test_nested_styles_reassert_the_outer_style() -> None:
    palette = Style()
    inner = StyleCode(palette, 36)
    outer = StyleCode(palette, 1)
    nested = outer(f"a {inner('b')} c")
    assert nested == f"\x1b[1ma \x1b[36mb{ANSI_RESET}\x1b[1m c{ANSI_RESET}"


def test_palette_starts_in_requested_state() -> None:
    assert Style(ansi_enabled=True).heading("x") == "\x1b[1mx\x1b[0m"
    assert Style(ansi_enabled=False).heading("x") == "x"


def test_toggling_palette_is_effective_for_held_style_references() -> None:
    palette = Style(ansi_enabled=True)
    # references captured before reconfiguration must reflect the change
    held_reference = palette.error

    palette.ansi_enabled = False
    assert held_reference("boom") == "boom"

    palette.ansi_enabled = True
    assert held_reference("boom") == "\x1b[91;1mboom\x1b[0m"


def test_child_io_snapshots_parent_ansi_setting() -> None:
    parent_io = PoeIO(output=io.StringIO(), ansi=True, make_default=False)
    child_io = PoeIO(parent=parent_io, make_default=False)
    assert child_io.ansi_enabled is True
    assert child_io.style is not parent_io.style

    # each PoeIO owns its palette, so configuring one doesn't affect the other
    child_io.configure(ansi_enabled=False)
    assert child_io.ansi_enabled is False
    assert parent_io.ansi_enabled is True


def test_child_io_ansi_arg_overrides_parent_setting() -> None:
    parent_io = PoeIO(output=io.StringIO(), ansi=True, make_default=False)
    child_io = PoeIO(parent=parent_io, ansi=False, make_default=False)
    assert child_io.ansi_enabled is False
    assert parent_io.ansi_enabled is True


def test_io_ansi_enabled_resolves_to_palette_state() -> None:
    poe_io = PoeIO(output=io.StringIO(), ansi=True, make_default=False)
    assert poe_io.ansi_enabled is poe_io.style.ansi_enabled is True

    poe_io.configure(ansi_enabled=False)
    assert poe_io.ansi_enabled is poe_io.style.ansi_enabled is False


def test_print_poe_action_output_bytes() -> None:
    """
    The action line's exact escape sequences are load bearing: they're also
    asserted (via subprocess output) in test_parallel_tasks.py.
    """
    error_stream = io.StringIO()
    poe_io = PoeIO(
        output=io.StringIO(), error=error_stream, ansi=True, make_default=False
    )
    poe_io.print_poe_action("=>", "echo hello")
    assert error_stream.getvalue() == (
        "\x1b[37mPoe =>\x1b[0m \x1b[94mecho hello\x1b[0m\n"
    )


def test_print_warning_prefix_styling() -> None:
    error_stream = io.StringIO()
    poe_io = PoeIO(
        output=io.StringIO(), error=error_stream, ansi=True, make_default=False
    )
    poe_io.print_warning("watch out")
    assert error_stream.getvalue() == "\x1b[91;1mWarning:\x1b[0m watch out\n"


def test_user_content_is_never_interpreted_or_stripped() -> None:
    """
    Unlike the former tag based system, content passed through PoeIO must not
    be parsed for markup, and embedded ANSI codes pass through untouched even
    when ansi is disabled.
    """
    output_stream = io.StringIO()
    poe_io = PoeIO(output=output_stream, ansi=False, make_default=False)
    poe_io.print("<em>not a tag</em> \\< \x1b[31mraw\x1b[0m")
    assert output_stream.getvalue() == "<em>not a tag</em> \\< \x1b[31mraw\x1b[0m\n"
