"""Account record schema.

Pure contract module: no I/O, no logging, no database, no pandas, no
model-layer imports.

An account is the top-level billing entity — a household or business
that owns one or more subscriber lines.  This module defines the
structural shape of an account record and the fixed vocabulary of
account statuses.  Validation runs through the shared ``_Validated``
mix-in (D30, D32).
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated

__all__ = ["ACCOUNT_STATUSES", "Account"]

ACCOUNT_STATUSES: tuple[str, ...] = ("active", "suspended", "closed")
"""Valid account lifecycle statuses.

- ``active``: account is in good standing.
- ``suspended``: temporarily paused (e.g. non-payment).
- ``closed``: permanently canceled.
"""


@dataclasses.dataclass(frozen=True)
class Account(_Validated):
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

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("account_id", str),
        ("account_ordinal", int, bool),
        ("billing_cycle_day", int, bool),
        ("region_code", str),
        ("account_status", str),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this account."""
        return (
            (
                bool(self.account_id.strip()),
                "account_id",
                self.account_id,
            ),
            (
                self.account_ordinal >= 0,
                "account_ordinal",
                self.account_ordinal,
            ),
            (
                1 <= self.billing_cycle_day <= 28,
                "billing_cycle_day",
                self.billing_cycle_day,
            ),
            (
                bool(self.region_code.strip()),
                "region_code",
                self.region_code,
            ),
            (
                self.account_status in ACCOUNT_STATUSES,
                "account_status",
                self.account_status,
            ),
        )
