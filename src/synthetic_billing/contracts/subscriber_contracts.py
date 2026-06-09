"""Subscriber record schema.

Pure contract module: no I/O, no logging, no database, no pandas, no
model-layer imports.

A subscriber is an individual service line under an account.  Each
subscriber holds exactly one plan at a time.  Semantic validation of
the plan code against a catalog happens at the model layer; this
contract enforces only structural shape rules.  Validation runs through
the shared ``_Validated`` mix-in (D30, D32).
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated

__all__ = ["Subscriber"]


@dataclasses.dataclass(frozen=True)
class Subscriber(_Validated):
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

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("subscriber_id", str),
        ("account_id", str),
        ("subscriber_ordinal", int, bool),
        ("plan_code", str),
        ("active", bool),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this subscriber."""
        return (
            (
                bool(self.subscriber_id.strip()),
                "subscriber_id",
                self.subscriber_id,
            ),
            (
                bool(self.account_id.strip()),
                "account_id",
                self.account_id,
            ),
            (
                self.subscriber_ordinal >= 0,
                "subscriber_ordinal",
                self.subscriber_ordinal,
            ),
            (
                bool(self.plan_code.strip()),
                "plan_code",
                self.plan_code,
            ),
        )
