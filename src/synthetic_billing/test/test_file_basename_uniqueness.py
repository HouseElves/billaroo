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

from synthetic_billing.test.repo_scan import find_project_root, is_ignored


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


def test_unique_file_basenames() -> None:
    """All file basenames in the project must be unique, with a general
    exception for wrapped-dunder Python files."""
    root = find_project_root()

    basenames: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if _is_wrapped_dunder_python_file(p):
            continue
        if is_ignored(p.relative_to(root)):
            continue
        basenames.append(p.name)

    counts = Counter(basenames)
    dupes = {name: cnt for name, cnt in counts.items() if cnt > 1}
    assert not dupes, f"Duplicate basenames found: {dupes}"
