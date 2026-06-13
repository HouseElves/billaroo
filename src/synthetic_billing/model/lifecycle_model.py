"""Lifecycle event builders.

This slice fixes the public boundary of the ``subscriber_cancelled``
lifecycle event builder (D38).  Concrete construction — deterministic
event-ID derivation, subscriber lookup against simulation state, plan
code resolution from the subscriber's active plan subscription — is
reserved for a later slice.

``build_subscriber_cancelled_event`` raises ``NotImplementedError``
immediately; its companion test asserts that boundary under
constitution rule 21.
"""

from __future__ import annotations

from synthetic_billing.actions.lifecycle_actions import CancelSubscriberIntent
from synthetic_billing.contracts.event_contracts import LifecycleEvent
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = ["build_subscriber_cancelled_event"]


def build_subscriber_cancelled_event(
    state: SimulationState,
    intent: CancelSubscriberIntent,
) -> LifecycleEvent:
    """Build the lifecycle event recording a subscriber cancellation.

    Concrete construction — deterministic event-ID derivation,
    subscriber lookup, plan code resolution — is reserved for a later
    slice (D38).  This entry point raises ``NotImplementedError``
    immediately and does not inspect either argument.
    """
    del state, intent
    raise NotImplementedError(
        "build_subscriber_cancelled_event is not implemented"
    )
