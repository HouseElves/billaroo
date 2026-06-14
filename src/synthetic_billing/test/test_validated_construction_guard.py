"""Project-level guard: validated records have one production construction boundary.

Design log D41.  Production code must build ``_Validated`` records
through ``ClassName.create_validated(...)`` or an established model
builder, never through a direct dataclass constructor call.  Direct
construction is a test-only escape hatch for creating deliberately
invalid instances.

This guard discovers the set of ``_Validated`` subclasses by parsing
the source tree (no manually duplicated class list), then scans
non-test production Python source for direct constructor calls to
those classes.  ``ClassName.create_validated(...)`` is permitted;
direct construction inside test source is permitted; ordinary
unrelated constructor calls are ignored.

Scope is deliberately small and non-adversarial (D41).  The guard
parses straightforward source such as::

    CancelSubscriberIntent(month, subscriber_id)

It does not resolve import aliases, reflection, dynamic imports,
``dataclasses.replace(...)``, or deliberately obscured construction.
It is a repository hygiene check, not a static-analysis framework.
"""

from __future__ import annotations

import ast
import pathlib

from synthetic_billing.test.repo_scan import find_project_root, is_ignored

# The base class whose subclasses are subject to the construction
# boundary.  Discovered by name from the AST: a class is treated as a
# validated record when it lists this identifier among its bases.
_VALIDATED_BASE = "_Validated"


def _is_test_source(relative_path: pathlib.Path) -> bool:
    """Return True for test source (a ``test`` package dir or test_*.py)."""
    if "test" in relative_path.parts:
        return True
    return relative_path.name.startswith("test_")


def _python_sources(root: pathlib.Path) -> list[pathlib.Path]:
    """Yield all non-ignored .py files under *root*."""
    return [
        p
        for p in root.rglob("*.py")
        if p.is_file() and not is_ignored(p.relative_to(root))
    ]


def _discover_validated_subclasses(
    sources: list[pathlib.Path],
) -> set[str]:
    """Return the names of every class that derives from ``_Validated``.

    Discovery is by direct base-name match in the AST.  This covers
    the project's flat one-level inheritance from ``_Validated`` (no
    intermediate validated base classes exist), which is sufficient
    for the current tree and intentionally simple (D41).
    """
    names: set[str] = set()
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {
                base.id
                for base in node.bases
                if isinstance(base, ast.Name)
            }
            if _VALIDATED_BASE in base_names:
                names.add(node.name)
    return names


def _direct_construction_violations(
    path: pathlib.Path,
    validated_names: set[str],
) -> list[tuple[int, str]]:
    """Return (line, class_name) for each direct validated-constructor call.

    A direct call is ``ClassName(...)`` where ``ClassName`` is a
    validated subclass.  ``ClassName.create_validated(...)`` is an
    attribute call, not a direct constructor call, so it never
    matches here.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in validated_names:
            violations.append((node.lineno, func.id))
    return violations


def test_no_direct_validated_construction_in_production() -> None:
    """Production source must not directly construct a ``_Validated`` subclass.

    Validated records are built through ``create_validated`` or a model
    builder in production code (D32, D41).  Direct construction is
    reserved for tests that need deliberately invalid instances.
    """
    root = find_project_root()
    sources = _python_sources(root)
    validated_names = _discover_validated_subclasses(sources)

    # The guard is meaningless if discovery found nothing; fail loudly
    # rather than passing vacuously.
    assert validated_names, "No _Validated subclasses discovered in source"

    offenders: list[str] = []
    for path in sources:
        relative = path.relative_to(root)
        if _is_test_source(relative):
            continue
        if path.name == "_validation.py":
            # Defines the base class and its helpers; never constructs
            # a concrete validated subclass.
            continue
        for line, class_name in _direct_construction_violations(
            path, validated_names,
        ):
            offenders.append(f"{relative}:{line}: {class_name}(...)")

    assert not offenders, (
        "Direct construction of _Validated subclasses found in "
        "production source (use ClassName.create_validated(...) or a "
        "model builder instead):\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# Behavioural tests on synthetic source (D41)
# ---------------------------------------------------------------------------
#
# The test above runs the guard against the real tree.  The tests below
# demonstrate the guard's observable behaviour on small synthetic source
# files: production direct construction is flagged, the equivalent test
# call is permitted, create_validated is permitted, and unrelated
# constructor calls are ignored.

_VALIDATED_MODULE_SOURCE = '''\
class _Validated:
    pass


class CancelSubscriberIntent(_Validated):
    simulation_month: int
    subscriber_id: str
'''


def _write(path: pathlib.Path, text: str) -> pathlib.Path:
    """Write *text* to *path*, creating parents, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _synthetic_validated_names(tmp_path: pathlib.Path) -> set[str]:
    """Discover validated subclass names from a written contracts module."""
    contracts = _write(tmp_path / "contracts.py", _VALIDATED_MODULE_SOURCE)
    return _discover_validated_subclasses([contracts])


def test_discovers_validated_subclass_without_manual_list(tmp_path) -> None:
    """Discovery finds the subclass by base name, with no hard-coded list."""
    names = _synthetic_validated_names(tmp_path)
    assert "CancelSubscriberIntent" in names
    assert "_Validated" not in names


def test_production_direct_construction_is_flagged(tmp_path) -> None:
    """A direct constructor call in production source is reported by line."""
    names = _synthetic_validated_names(tmp_path)
    prod = _write(
        tmp_path / "behavior_model.py",
        "from contracts import CancelSubscriberIntent\n"
        "def choose():\n"
        "    return CancelSubscriberIntent(2, 'sub-1')\n",
    )
    assert _direct_construction_violations(prod, names) == [
        (3, "CancelSubscriberIntent"),
    ]


def test_create_validated_is_permitted(tmp_path) -> None:
    """A create_validated call is not a direct constructor call."""
    names = _synthetic_validated_names(tmp_path)
    prod = _write(
        tmp_path / "month_driver.py",
        "from contracts import CancelSubscriberIntent\n"
        "def choose():\n"
        "    return CancelSubscriberIntent.create_validated(2, 'sub-1')\n",
    )
    assert not _direct_construction_violations(prod, names)


def test_unrelated_constructor_call_is_not_flagged(tmp_path) -> None:
    """An ordinary, non-validated constructor call is ignored."""
    names = _synthetic_validated_names(tmp_path)
    prod = _write(
        tmp_path / "other.py",
        "class Plain:\n"
        "    pass\n"
        "def make_plain():\n"
        "    return Plain()\n",
    )
    assert not _direct_construction_violations(prod, names)


def test_test_source_classification_permits_direct_construction(
    tmp_path,
) -> None:
    """Files classified as tests are skipped, permitting direct construction.

    Covers both the ``test_`` filename form and the ``test`` package-dir
    form; a plain module is not classified as test.
    """
    test_file = tmp_path / "test_thing.py"
    package_test_file = tmp_path / "test" / "test_in_pkg.py"
    plain_module = tmp_path / "plain_module.py"
    _write(test_file, "x = 1\n")
    _write(package_test_file, "x = 1\n")
    _write(plain_module, "x = 1\n")

    assert _is_test_source(test_file.relative_to(tmp_path)) is True
    assert _is_test_source(package_test_file.relative_to(tmp_path)) is True
    assert _is_test_source(plain_module.relative_to(tmp_path)) is False
