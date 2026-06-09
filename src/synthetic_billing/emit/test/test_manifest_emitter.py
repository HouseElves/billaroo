"""Tests for manifest_emitter.py.

Verifies deterministic manifest construction and file writing: fixed
format version, preserved file order, exact record counts, stable JSON
text with a trailing newline, and idempotent rerun behavior.
"""

from __future__ import annotations

import json

from synthetic_billing.emit.manifest_emitter import (
    FORMAT_VERSION,
    MANIFEST_FILENAME,
    build_manifest,
    emit_manifest,
)


class TestBuildManifest:
    """build_manifest produces the expected mapping."""

    def test_format_version(self) -> None:
        """The manifest records the module format version."""
        manifest = build_manifest([("accounts.csv", 3)])
        assert manifest["format_version"] == FORMAT_VERSION

    def test_file_entries(self) -> None:
        """Each (name, count) pair becomes a name/record_count entry."""
        manifest = build_manifest(
            [("accounts.csv", 2), ("subscribers.csv", 5)]
        )
        assert manifest["files"] == [
            {"name": "accounts.csv", "record_count": 2},
            {"name": "subscribers.csv", "record_count": 5},
        ]

    def test_order_preserved(self) -> None:
        """File entry order follows the input sequence order."""
        manifest = build_manifest(
            [("c.csv", 1), ("a.csv", 1), ("b.csv", 1)]
        )
        names = [entry["name"] for entry in manifest["files"]]
        assert names == ["c.csv", "a.csv", "b.csv"]

    def test_empty_files(self) -> None:
        """An empty file list yields an empty files array."""
        manifest = build_manifest([])
        assert manifest == {"format_version": FORMAT_VERSION, "files": []}


class TestEmitManifest:
    """emit_manifest writes a deterministic manifest file."""

    def test_writes_manifest_file(self, tmp_path) -> None:
        """emit_manifest writes manifest.json into the output directory."""
        path = emit_manifest(tmp_path, [("accounts.csv", 1)])
        assert path == tmp_path / MANIFEST_FILENAME
        assert path.exists()

    def test_content_parses_to_expected(self, tmp_path) -> None:
        """The written JSON parses back to the built manifest mapping."""
        files = [("accounts.csv", 2), ("subscriptions.csv", 3)]
        path = emit_manifest(tmp_path, files)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == build_manifest(files)

    def test_trailing_newline(self, tmp_path) -> None:
        """The manifest text ends with exactly one trailing newline."""
        path = emit_manifest(tmp_path, [("accounts.csv", 1)])
        text = path.read_text(encoding="utf-8")
        assert text.endswith("}\n")
        assert not text.endswith("}\n\n")

    def test_indented(self, tmp_path) -> None:
        """The manifest is human-readable with two-space indentation."""
        path = emit_manifest(tmp_path, [("accounts.csv", 1)])
        text = path.read_text(encoding="utf-8")
        assert '\n  "format_version": 1' in text

    def test_rerun_deterministic(self, tmp_path) -> None:
        """Re-emitting the same input overwrites with identical bytes."""
        files = [("accounts.csv", 2), ("subscribers.csv", 2)]
        first = emit_manifest(tmp_path, files).read_bytes()
        second = emit_manifest(tmp_path, files).read_bytes()
        assert first == second

    def test_overwrite_replaces_prior(self, tmp_path) -> None:
        """A second emission with different counts replaces the first."""
        emit_manifest(tmp_path, [("accounts.csv", 1)])
        path = emit_manifest(tmp_path, [("accounts.csv", 9)])
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["files"][0]["record_count"] == 9
