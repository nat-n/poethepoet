from io import StringIO

from poethepoet.exceptions import ExecutionError, PoeException
from poethepoet.io import PoeIO
from poethepoet.ui import PoeUi


def render_error(error):
    output = StringIO()
    PoeUi(io=PoeIO(output=output, error=output, make_default=False)).print_error(error)
    return output.getvalue()


def test_single_level_cause_unchanged():
    assert render_error(ExecutionError("Outer", ValueError("inner"))) == (
        "Error: Outer\n     | From: inner\n"
    )


def test_multi_level_causes_render_one_line_each():
    error = ExecutionError(
        "Outer", ExecutionError("Middle", ExecutionError("Innermost"))
    )
    assert render_error(error) == (
        "Error: Outer\n     | From: Middle\n     | From: Innermost\n"
    )


def test_poe_exception_cause_in_chain():
    assert render_error(ExecutionError("Outer", PoeException("Config broke"))) == (
        "Error: Outer\n     | From: Config broke\n"
    )
