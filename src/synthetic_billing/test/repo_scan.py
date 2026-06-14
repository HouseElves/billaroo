"""Shared repository-scan helpers for project-level guard tests.

Project-wide guards (basename uniqueness, validated-construction)
need the same primitives: locate the repository root, decide whether
a path lives under an ignored directory, and walk the source tree.
Centralising them here keeps the individual guard tests focused on
their specific rule and avoids duplicated scan logic.

This module is deliberately not named ``test_*``: it holds helpers,
not tests, so pytest does not collect it as a test module.
"""

from __future__ import annotations

import pathlib

IGNORE_DIRS = frozenset({
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "build",
    "dist",
    "target",
    "logs",
})


def find_project_root() -> pathlib.Path:
    """Walk up from this file until we find pyproject.toml."""
    current = pathlib.Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not locate project root (no pyproject.toml found)")


def is_ignored(relative_path: pathlib.Path) -> bool:
    """Return True if *relative_path* falls under an ignored directory."""
    for part in relative_path.parts:
        if part in IGNORE_DIRS:
            return True
        if part.endswith(".egg-info"):
            return True
    return False
