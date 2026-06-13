"""Lifecycle semantic intents and the cancellation chain entry point.

This slice introduces only the cancellation intent and its
chain-builder entry point (D38).  The intent carries the minimum
identity needed to express a cancellation decision — the simulation
month it occurred in and the subscriber identifier — and nothing more.
Owning account, plan code, deterministic event ID, and RNG state are
resolved from simulation state by later implementation; embedding them
in the intent would pre-bake derivation logic that does not yet exist.

The chain-builder entry point is a deliberately unimplemented stub.
Its companion test asserts the boundary (constitution rule 21).  No
action execution, state mutation, or event construction happens here.
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
from synthetic_billing.actions.action_protocols import SemanticAction

__all__ = [
    "CancelSubscriberIntent",
    "build_cancel_subscriber_action_chain",
]


@dataclasses.dataclass(frozen=True)
class CancelSubscriberIntent(_Validated):
    """A semantic intent to cancel a single subscriber in one month.

    Attributes:
        simulation_month: Simulation month the cancellation occurs in.
            Must be at least ``2``: month ``1`` is the
            starter-population month and never produces cancellations
            (D38).
        subscriber_id: Subscriber the cancellation applies to.
    """

    simulation_month: int
    subscriber_id: str

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("simulation_month", int, bool),
        ("subscriber_id", str),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this intent."""
        return (
            (
                self.simulation_month >= 2,
                "simulation_month",
                self.simulation_month,
            ),
            (
                bool(self.subscriber_id.strip()),
                "subscriber_id",
                self.subscriber_id,
            ),
        )


def build_cancel_subscriber_action_chain(
    intent: CancelSubscriberIntent,
) -> tuple[SemanticAction, ...]:
    """Build the ordered action chain that expresses a cancellation.

    The chain composition (close active subscriptions, deactivate the
    subscriber, emit the lifecycle event, and so on) is reserved for a
    later slice (D38).  This entry point exists in this slice only to
    fix the public boundary; it raises ``NotImplementedError``
    immediately and does not inspect ``intent``.
    """
    del intent
    raise NotImplementedError(
        "build_cancel_subscriber_action_chain is not implemented"
    )
