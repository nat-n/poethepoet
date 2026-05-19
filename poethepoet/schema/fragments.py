"""
Cross-cutting JSON Schema fragments that aren't owned by any single
PoeOptions class — the task_def union (incl. forward-compat fallback),
the executor tagged union, env/envfile value polymorphism, and the
patternProperties for the tasks/groups maps.
"""

from __future__ import annotations

# Implementation lands in Tasks 13–16.
