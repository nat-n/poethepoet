"""
TypeAnnotation → JSON Schema translation.

Each `TypeAnnotation` subclass is translated by a corresponding function.
The translator does not know about poe domain shapes (tasks, executors,
etc.); it only emits the structural JSON Schema corresponding to a type
annotation. Cross-cutting compositions live in `fragments.py`.
"""

from __future__ import annotations

# Implementation lands in Tasks 5–7.
