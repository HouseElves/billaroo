"""Account record schema.

Pure contract module: no I/O, no logging, no database, no pandas.

An account is the top-level billing entity — a household or business
that owns one or more subscriber lines.  This module defines the
structural shape of an account record and the fixed vocabulary of
account statuses.
"""

# pylint: disable=duplicate-code
# Reason: account and subscriber contracts intentionally duplicate the tiny
# validation helpers for now. D29 records this as real pressure toward a future
# shared validation vocabulary, but extraction is premature until another
# contract module repeats the pattern.

from __future__ import annotations

import dataclasses

__all__ = ["ACCOUNT_STATUSES", "Account"]

ACCOUNT_STATUSES: tuple[str, ...] = ("active", "suspended", "closed")
"""Valid account lifecycle statuses.

- ``active``: account is in good standing.
- ``suspended``: temporarily paused (e.g. non-payment).
- ``closed``: permanently canceled.
"""


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
class Account:
    """A billing account record.

    Attributes:
        account_id: Deterministic hex identifier (see D28).
        account_ordinal: Zero-based generation index within a scenario.
        billing_cycle_day: Day of the month invoices close (1–28).
        region_code: Short region identifier (e.g. ``"US-WEST"``).
        account_status: One of :data:`ACCOUNT_STATUSES`.
    """

    account_id: str
    account_ordinal: int
    billing_cycle_day: int
    region_code: str
    account_status: str

    def __post_init__(self) -> None:
        _validate_non_blank("account_id", self.account_id)
        _validate_ordinal("account_ordinal", self.account_ordinal)

        if isinstance(self.billing_cycle_day, bool):
            raise TypeError("billing_cycle_day must be int, not bool")
        if not isinstance(self.billing_cycle_day, int):
            raise TypeError(
                f"billing_cycle_day must be int, got "
                f"{type(self.billing_cycle_day).__name__}"
            )
        if not 1 <= self.billing_cycle_day <= 28:
            raise ValueError(
                f"billing_cycle_day must be 1..28, got "
                f"{self.billing_cycle_day}"
            )

        _validate_non_blank("region_code", self.region_code)

        if not isinstance(self.account_status, str):
            raise TypeError(
                f"account_status must be str, got "
                f"{type(self.account_status).__name__}"
            )
        if self.account_status not in ACCOUNT_STATUSES:
            raise ValueError(
                f"account_status must be one of {ACCOUNT_STATUSES}, "
                f"got {self.account_status!r}"
            )
