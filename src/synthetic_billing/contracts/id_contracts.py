"""Deterministic identifier derivation.

Pure contract module: no I/O, no logging, no database, no pandas.

IDs are the first 16 lowercase hex characters of the SHA-256 digest of
the canonical fields joined with ``":"``.  By convention the first
field is an entity-type prefix (e.g. ``"account"``, ``"subscriber"``,
``"invoice"``) so IDs from different entity families cannot collide.

See design log entry D28 for the rationale on the SHA-256/16-hex scheme.
"""

from __future__ import annotations

import hashlib

__all__ = ["derive_id"]


_ID_HEX_LENGTH = 16
_FIELD_SEPARATOR = ":"


def derive_id(*fields: str | int) -> str:
    """Derive a 16-hex-character deterministic ID from canonical fields.

    Each field must be either a non-blank string that does not contain
    the ``":"`` separator, or a non-negative integer ordinal.  ``bool``
    is rejected explicitly because ``isinstance(True, int)`` is True
    in Python and silent bool-as-ordinal would be a quiet correctness
    hazard.

    Args:
        *fields: Canonical fields, joined with ``":"`` before hashing.

    Returns:
        A 16-character lowercase hex string.

    Raises:
        ValueError: If no fields are provided, a string field is blank
            or contains ``":"``, or an integer field is negative.
        TypeError: If a field is not a ``str`` or ``int`` (or is a
            ``bool``).
    """
    if not fields:
        raise ValueError("derive_id requires at least one field")
    canonical = _FIELD_SEPARATOR.join(_canonicalize_field(f) for f in fields)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:_ID_HEX_LENGTH]


def _canonicalize_field(value: object) -> str:
    """Return the canonical string form of *value* for ID hashing.

    Strings pass through unchanged after validation.  Non-negative
    integers are rendered with ``str()``.  Everything else raises.
    """
    if isinstance(value, bool):
        raise TypeError(f"bool is not a valid id field: {value!r}")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(
                f"ordinal id field must be non-negative, got {value}"
            )
        return str(value)
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("string id field must not be blank")
        if _FIELD_SEPARATOR in value:
            raise ValueError(
                f"string id field must not contain {_FIELD_SEPARATOR!r}: "
                f"{value!r}"
            )
        return value
    raise TypeError(
        f"id field must be str or int, got {type(value).__name__}"
    )
