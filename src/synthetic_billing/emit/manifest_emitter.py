"""Deterministic raw-emission manifest writer.

A manifest is a small JSON document describing a single raw-emission
batch: a format version and the list of emitted files with their
record counts.  It is the index downstream loaders read to discover
what was emitted.

The manifest is intentionally minimal (D34).  It records only
``format_version`` and per-file ``record_count`` values.  It contains
no wall-clock timestamps: the project has no deterministic clock
abstraction yet, and a wall-clock field would break byte-for-byte
reproducibility (D2).  When a deterministic clock lands, a timestamp
field becomes a separate decision.

Stdlib only: ``json`` and ``pathlib``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

__all__ = [
    "FORMAT_VERSION",
    "MANIFEST_FILENAME",
    "build_manifest",
    "emit_manifest",
]

FORMAT_VERSION: int = 1
MANIFEST_FILENAME: str = "manifest.json"

# Declared grain (constitution rule 15):
#
# - manifest.json: one manifest document per raw emission batch.
# - Within the manifest's ``files`` array: one entry per emitted raw
#   data file (currently accounts.csv, subscribers.csv,
#   subscriptions.csv).
#
# A new emission batch overwrites the prior manifest deterministically;
# the manifest never accumulates entries across batches.


def build_manifest(files: Sequence[tuple[str, int]]) -> dict:
    """Build the manifest mapping for a raw-emission batch.

    Args:
        files: Ordered sequence of ``(filename, record_count)`` pairs.
            The order is preserved in the emitted ``files`` array.

    Returns:
        A plain ``dict`` ready for deterministic JSON serialization.
        Key order is fixed: ``format_version`` then ``files``; each
        file entry is ``name`` then ``record_count``.
    """
    return {
        "format_version": FORMAT_VERSION,
        "files": [
            {"name": name, "record_count": record_count}
            for name, record_count in files
        ],
    }


def emit_manifest(
    output_dir: Path,
    files: Sequence[tuple[str, int]],
) -> Path:
    """Write ``manifest.json`` into *output_dir* and return its path.

    The JSON is rendered with two-space indentation and a trailing
    newline, in Unix newline style, with key order fixed by
    :func:`build_manifest`.  An existing manifest is overwritten
    deterministically.

    Args:
        output_dir: Directory the manifest is written into.  Assumed
            to exist (the raw emitter creates it).
        files: Ordered ``(filename, record_count)`` pairs.

    Returns:
        The path to the written manifest file.
    """
    manifest_path = output_dir / MANIFEST_FILENAME
    text = json.dumps(build_manifest(files), indent=2) + "\n"
    manifest_path.write_text(text, encoding="utf-8", newline="\n")
    return manifest_path
