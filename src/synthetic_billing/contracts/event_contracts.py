"""Lifecycle event record schema.

Pure contract module: no I/O, no logging, no database, no pandas, no
model-layer imports.

A ``LifecycleEvent`` is the operational record emitted when a semantic
lifecycle transition occurs after the starter-population month.  This
module introduces only the ``subscriber_cancelled`` event type; new
event types are added when concrete implementation pressure justifies
them (D38).

Construction of lifecycle events from simulation state lives in the
model layer (``model/lifecycle_model.py``).  This contract module only
defines the event vocabulary and its structural shape (D15, D38).
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated

__all__ = [
    "LIFECYCLE_EVENT_TYPES",
    "LifecycleEvent",
    "SUBSCRIBER_CANCELLED_EVENT_TYPE",
]


SUBSCRIBER_CANCELLED_EVENT_TYPE: str = "subscriber_cancelled"
"""Lifecycle event type emitted when a subscriber cancels (D38)."""


LIFECYCLE_EVENT_TYPES: tuple[str, ...] = (SUBSCRIBER_CANCELLED_EVENT_TYPE,)
"""All currently accepted lifecycle event types.

This tuple is intentionally minimal.  Additional event types are
introduced only when concrete behaviour to emit them is also added
(D38, constitution rule 22).
"""


# Lifecycle events have six identifying fields by design.  Reducing them
# further would conflate the audit grain with derived analytics; rule 15
# requires the grain to be declared, not collapsed.
@dataclasses.dataclass(frozen=True)
class LifecycleEvent(_Validated):  # pylint: disable=too-many-instance-attributes
    """A semantic lifecycle event for a single subscriber in a single month.

    Attributes:
        event_id: Deterministic identifier for this lifecycle event.
        simulation_month: Simulation month the event occurred in.  Must
            be at least ``2``: month ``1`` is the starter-population
            month and never produces lifecycle events (D38).
        event_type: One of :data:`LIFECYCLE_EVENT_TYPES`.
        account_id: Owning account identifier.
        subscriber_id: Subscriber the event applies to.
        plan_code: Plan code the subscriber was on at the moment the
            event was emitted.
    """

    event_id: str
    simulation_month: int
    event_type: str
    account_id: str
    subscriber_id: str
    plan_code: str

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("event_id", str),
        ("simulation_month", int, bool),
        ("event_type", str),
        ("account_id", str),
        ("subscriber_id", str),
        ("plan_code", str),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this lifecycle event."""
        return (
            (
                bool(self.event_id.strip()),
                "event_id",
                self.event_id,
            ),
            (
                self.simulation_month >= 2,
                "simulation_month",
                self.simulation_month,
            ),
            (
                self.event_type in LIFECYCLE_EVENT_TYPES,
                "event_type",
                self.event_type,
            ),
            (
                bool(self.account_id.strip()),
                "account_id",
                self.account_id,
            ),
            (
                bool(self.subscriber_id.strip()),
                "subscriber_id",
                self.subscriber_id,
            ),
            (
                bool(self.plan_code.strip()),
                "plan_code",
                self.plan_code,
            ),
        )
