"""
Orchestrator: walks ProjectConfig.ConfigOptions and the PoeTask /
PoeExecutor registries, calls __schema_fragment__ hooks, and assembles
the complete root schema.
"""

from __future__ import annotations


def build_schema() -> dict:
    """
    Build the complete JSON Schema for the `tool.poe` subtable.

    Returns a self-contained draft-07 schema as a dict. Stable across
    runs (deterministic key order) so committed output diffs cleanly.
    """
    # Placeholder until Task 17 lands.
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://json.schemastore.org/partial-poe.json",
        "type": "object",
    }
