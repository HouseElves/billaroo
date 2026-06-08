"""Subscription record schema.

Pure contract module: no I/O, no logging, no database, no pandas, no
model-layer imports.

A subscription is an effective-dated entitlement connecting a subscriber
to an item (plan or feature).  Each subscription tracks when the
entitlement began, when (if ever) it ended, and its current status.

This is the first domain contract to use the shared ``_Validated``
vocabulary (D30, D31).  Type checking is declared via
``_type_check_specs`` and structural validation via
``_structural_checks``.  Catalog membership and feature/plan
compatibility checks live in the model builder, not here (D15).
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated

__all__ = [
    "ACTIVE_SUBSCRIPTION_STATUS",
    "ENDED_SUBSCRIPTION_STATUS",
    "FEATURE_ITEM_TYPE",
    "PLAN_ITEM_TYPE",
    "SUBSCRIPTION_ITEM_TYPES",
    "SUBSCRIPTION_STATUSES",
    "Subscription",
]

PLAN_ITEM_TYPE: str = "plan"
FEATURE_ITEM_TYPE: str = "feature"
SUBSCRIPTION_ITEM_TYPES: tuple[str, ...] = (PLAN_ITEM_TYPE, FEATURE_ITEM_TYPE)

ACTIVE_SUBSCRIPTION_STATUS: str = "active"
ENDED_SUBSCRIPTION_STATUS: str = "ended"
SUBSCRIPTION_STATUSES: tuple[str, ...] = (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
)


@dataclasses.dataclass(frozen=True)
class Subscription(_Validated):
    """An effective-dated entitlement linking a subscriber to an item.

    Attributes:
        subscription_id: Deterministic hex identifier (D28).
        subscriber_id: Parent subscriber identifier.
        item_type: ``"plan"`` or ``"feature"``.
        item_code: The plan or feature code this subscription covers.
        start_month: Simulation month the subscription became active
            (1-indexed).
        end_month: Simulation month the subscription ended, or ``None``
            if still active.
        subscription_status: ``"active"`` or ``"ended"``.
    """

    subscription_id: str
    subscriber_id: str
    item_type: str
    item_code: str
    start_month: int
    end_month: int | None
    subscription_status: str

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("subscription_id", str),
        ("subscriber_id", str),
        ("item_type", str),
        ("item_code", str),
        ("start_month", int, bool),
        ("end_month", (int, type(None)), bool),
        ("subscription_status", str),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this subscription."""
        checks: list[CheckTuple] = [
            (
                bool(self.subscription_id.strip()),
                "subscription_id",
                self.subscription_id,
            ),
            (
                bool(self.subscriber_id.strip()),
                "subscriber_id",
                self.subscriber_id,
            ),
            (
                self.item_type in SUBSCRIPTION_ITEM_TYPES,
                "item_type",
                self.item_type,
            ),
            (
                bool(self.item_code.strip()),
                "item_code",
                self.item_code,
            ),
            (
                self.start_month >= 1,
                "start_month",
                self.start_month,
            ),
            (
                self.subscription_status in SUBSCRIPTION_STATUSES,
                "subscription_status",
                self.subscription_status,
            ),
        ]

        if self.end_month is not None:
            checks.append(
                (
                    self.end_month >= self.start_month,
                    "end_month",
                    self.end_month,
                )
            )

        if self.subscription_status == ACTIVE_SUBSCRIPTION_STATUS:
            checks.append(
                (self.end_month is None, "end_month", self.end_month)
            )
        elif self.subscription_status == ENDED_SUBSCRIPTION_STATUS:
            checks.append(
                (self.end_month is not None, "end_month", self.end_month)
            )

        return tuple(checks)
