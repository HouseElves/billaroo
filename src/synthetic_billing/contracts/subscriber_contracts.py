"""Subscriber record schema.

Pure contract module: no I/O, no logging, no database, no pandas.

A subscriber is an individual service line under an account.  Each
subscriber holds exactly one plan at a time.  Semantic validation of
the plan code against a catalog happens at the model layer; this
contract enforces only structural shape rules.
"""

from __future__ import annotations

import dataclasses

__all__ = ["Subscriber"]


def _validate_non_blank(name: str, value: object) -> None:
    """Check that *value* is a non-blank string."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_ordinal(name: str, value: object) -> None:
    """Check that *value* is a non-negative int, rejecting bool."""
    if isinstance(value, bool):
        raise TypeError(f"{name} must be int, not bool")
    if not isinstance(value, int):
        raise TypeError(f"{name} must be int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")


@dataclasses.dataclass(frozen=True)
class Subscriber:
    """A subscriber service-line record.

    Attributes:
        subscriber_id: Deterministic hex identifier (see D28).
        account_id: Parent account identifier.
        subscriber_ordinal: Zero-based index within the parent account.
        plan_code: Current plan code.  Must be non-blank here;
            existence in a catalog is validated at the model layer.
        active: Whether this subscriber line is currently active.
    """

    subscriber_id: str
    account_id: str
    subscriber_ordinal: int
    plan_code: str
    active: bool

    def __post_init__(self) -> None:
        _validate_non_blank("subscriber_id", self.subscriber_id)
        _validate_non_blank("account_id", self.account_id)
        _validate_ordinal("subscriber_ordinal", self.subscriber_ordinal)
        _validate_non_blank("plan_code", self.plan_code)
        if not isinstance(self.active, bool):
            raise TypeError(
                f"active must be bool, got {type(self.active).__name__}"
            )
