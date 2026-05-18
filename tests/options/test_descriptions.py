"""
Tests for PoeOptions.description_for_field — class-attribute docstring
extraction.
"""

from poethepoet.options import PoeOptions


class DescribedOptions(PoeOptions):
    foo: str = ""
    """The foo field — should be discoverable."""

    bar: int = 0
    """Multi-line description
    spanning two lines."""

    baz: bool = False  # no docstring


class ChildOptions(DescribedOptions):
    foo: str = "override"
    """Overridden description for foo."""

    qux: str = ""
    """Qux on the child only."""


class GrandchildOptions(ChildOptions):
    """Class-level docstring; not a field docstring."""

    # foo is inherited from ChildOptions; description should follow MRO
    new_field: str = ""
    """A field defined only here."""


def test_description_extracted_from_simple_docstring():
    assert (
        DescribedOptions.description_for_field("foo")
        == "The foo field — should be discoverable."
    )


def test_description_extracted_from_multiline_docstring():
    description = DescribedOptions.description_for_field("bar")
    assert description is not None
    assert "Multi-line description" in description
    assert "spanning two lines" in description


def test_description_is_none_when_no_docstring():
    assert DescribedOptions.description_for_field("baz") is None


def test_description_returns_none_for_unknown_field():
    assert DescribedOptions.description_for_field("nonexistent") is None


def test_subclass_override_takes_precedence():
    assert (
        ChildOptions.description_for_field("foo") == "Overridden description for foo."
    )


def test_subclass_own_field_resolved():
    assert ChildOptions.description_for_field("qux") == "Qux on the child only."


def test_inherited_field_resolves_to_parent_docstring():
    # GrandchildOptions doesn't redeclare foo; the description should
    # come from ChildOptions (the nearest ancestor that defines it).
    assert (
        GrandchildOptions.description_for_field("foo")
        == "Overridden description for foo."
    )


def test_class_docstring_is_not_treated_as_field_description():
    # GrandchildOptions has a class docstring but it's not a field doc.
    # Looking up the first real field should still work.
    assert (
        GrandchildOptions.description_for_field("new_field")
        == "A field defined only here."
    )


def test_description_cache_is_populated_per_class():
    """
    The first call should populate a per-class cache.
    """
    # Trigger a lookup
    DescribedOptions.description_for_field("foo")
    # Cache attribute is set on the class's own __dict__ (not inherited).
    assert "_poe_field_descriptions" in DescribedOptions.__dict__
