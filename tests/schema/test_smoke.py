"""
Phase 2 smoke test — verifies the schema package layout is importable.
This file is intentionally not marked `schema` (it's a fast smoke check).
"""


def test_package_imports() -> None:
    from poethepoet.schema import build_schema

    assert callable(build_schema)


def test_package_submodules_importable() -> None:
    # These are the submodules subsequent tasks will populate.
    import poethepoet.schema.context  # noqa: F401
    import poethepoet.schema.fragments  # noqa: F401
    import poethepoet.schema.generator  # noqa: F401
    import poethepoet.schema.translate  # noqa: F401
