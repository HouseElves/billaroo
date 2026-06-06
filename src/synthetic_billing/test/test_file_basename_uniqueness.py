"""Project-level check: every file basename must be unique.

Design constitution rule 18: Do not create two files with the same
basename in different directories.

Scans from the project root.  Ignores generated/tool directories and
allows standard Python wrapped-dunder files (``__init__.py``,
``__main__.py``, etc.) that are expected to repeat at every package
level.
"""

import pathlib
from collections import Counter

_IGNORE_DIRS = frozenset({
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


def _is_wrapped_dunder_python_file(path: pathlib.Path) -> bool:
    """A .py file whose stem is wrapped in double underscores, e.g.
    ``__init__.py``, ``__main__.py``, ``__about__.py``.

    These files are exempt from the unique-basename rule because the
    Python package layout convention requires them to repeat at every
    package level.
    """
    return (
        path.suffix == ".py"
        and path.stem.startswith("__")
        and path.stem.endswith("__")
        and len(path.stem) > 4
    )


def _is_ignored(path: pathlib.Path) -> bool:
    """Return True if *path* falls under an ignored directory."""
    for part in path.parts:
        if part in _IGNORE_DIRS:
            return True
        if part.endswith(".egg-info"):
            return True
    return False


def _find_project_root() -> pathlib.Path:
    """Walk up from this file until we find pyproject.toml."""
    current = pathlib.Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not locate project root (no pyproject.toml found)")


def test_unique_file_basenames() -> None:
    """All file basenames in the project must be unique, with a general
    exception for wrapped-dunder Python files."""
    root = _find_project_root()

    basenames: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if _is_wrapped_dunder_python_file(p):
            continue
        if _is_ignored(p.relative_to(root)):
            continue
        basenames.append(p.name)

    counts = Counter(basenames)
    dupes = {name: cnt for name, cnt in counts.items() if cnt > 1}
    assert not dupes, f"Duplicate basenames found: {dupes}"
