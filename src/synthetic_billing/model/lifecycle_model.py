"""Lifecycle event builders.

This module owns construction of frozen lifecycle event records from
post-transition simulation state.  It is read-only over state: it
inspects what just changed and synthesises the audit fact.

The current event builder is the cancellation builder.  Additional
event builders (upgrade, downgrade, reactivation, feature change) are
introduced when their concrete construction logic is also added (D38).

The ``CancelSubscriberIntent`` reference is import-only under
``TYPE_CHECKING``.  At runtime this module never imports the
``actions`` layer; that makes the runtime import graph acyclic, which
matters because the cancellation action in ``actions.lifecycle_actions``
itself imports this builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
    PLAN_ITEM_TYPE,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.simulate.simulation_state import SimulationState

if TYPE_CHECKING:
    from synthetic_billing.actions.lifecycle_actions import (
        CancelSubscriberIntent,
    )

__all__ = ["build_subscriber_cancelled_event"]


def build_subscriber_cancelled_event(
    state: SimulationState,
    intent: CancelSubscriberIntent,
) -> LifecycleEvent:
    """Build the lifecycle event recording a subscriber cancellation (D39).

    The state passed in must be the post-cancellation state:

    * the subscriber is inactive;
    * the subscriber has no remaining active plan or feature
      subscriptions;
    * exactly one plan subscription belonging to the subscriber has
      ``end_month`` equal to ``intent.simulation_month``, with an
      ``item_code`` matching the subscriber's retained ``plan_code``;
    * that matching plan's effective range is non-empty and
      forward-going, i.e. ``start_month < end_month``.

    Event ID derivation follows the canonical order required by D38::

        derive_id(
            "lifecycle_event",
            "subscriber_cancelled",
            subscriber_id,
            simulation_month,
        )

    Args:
        state: Post-cancellation simulation state.
        intent: The cancellation intent that drove the chain.

    Returns:
        A validated :class:`LifecycleEvent`.

    Raises:
        InvalidRequestError: When the state does not unambiguously
            prove that the subscriber was cancelled in the intent
            month.
    """
    subscriber = _find_inactive_subscriber(state, intent.subscriber_id)
    _reject_remaining_active_subscriptions(state, intent.subscriber_id)
    ended_plan = _find_unique_cancellation_plan(
        state, intent.subscriber_id, intent.simulation_month,
    )
    if ended_plan.start_month >= ended_plan.end_month:
        raise InvalidRequestError(
            "Ended plan subscription has an empty or reversed effective "
            f"range [{ended_plan.start_month}, {ended_plan.end_month})",
            violations=(
                ("start_month", ended_plan.start_month),
                ("end_month", ended_plan.end_month),
            ),
        )
    if ended_plan.item_code != subscriber.plan_code:
        raise InvalidRequestError(
            "Ended plan subscription item_code disagrees with "
            "subscriber.plan_code",
            violations=(
                ("plan_code", subscriber.plan_code),
                ("item_code", ended_plan.item_code),
            ),
        )

    event_id = derive_id(
        "lifecycle_event",
        SUBSCRIBER_CANCELLED_EVENT_TYPE,
        intent.subscriber_id,
        intent.simulation_month,
    )

    return LifecycleEvent.create_validated(
        event_id,
        intent.simulation_month,
        SUBSCRIBER_CANCELLED_EVENT_TYPE,
        subscriber.account_id,
        intent.subscriber_id,
        subscriber.plan_code,
    )


def _find_subscriber_by_id_or_raise(
    state: SimulationState,
    subscriber_id: str,
):
    """Return the subscriber with this id from state, raising if absent.

    Subscriber-id uniqueness inside :class:`SimulationState` is
    enforced by state validation, so any present match is the unique
    one.  This helper is shared with the cancellation action layer to
    avoid duplicating the lookup-and-raise pattern.
    """
    matches = [
        s for s in state.subscribers if s.subscriber_id == subscriber_id
    ]
    if not matches:
        raise InvalidRequestError(
            f"Subscriber {subscriber_id} not present in state",
            violations=(("subscriber_id", subscriber_id),),
        )
    return matches[0]


def _find_inactive_subscriber(
    state: SimulationState,
    subscriber_id: str,
):
    """Return the subscriber, asserting it exists and is now inactive."""
    subscriber = _find_subscriber_by_id_or_raise(state, subscriber_id)
    if subscriber.active:
        raise InvalidRequestError(
            f"Subscriber {subscriber_id} is still active in the "
            "post-cancellation state",
            violations=(("active", subscriber.active),),
        )
    return subscriber


def _find_unique_cancellation_plan(
    state: SimulationState,
    subscriber_id: str,
    simulation_month: int,
):
    """Return the single plan subscription that ended this month."""
    ended_plans = [
        s for s in state.subscriptions
        if s.subscriber_id == subscriber_id
        and s.item_type == PLAN_ITEM_TYPE
        and s.subscription_status == ENDED_SUBSCRIPTION_STATUS
        and s.end_month == simulation_month
    ]
    if len(ended_plans) != 1:
        raise InvalidRequestError(
            "Post-cancellation state must contain exactly one plan "
            f"subscription for {subscriber_id} ended in month "
            f"{simulation_month}",
            violations=(
                ("ended_plan_count", len(ended_plans)),
            ),
        )
    return ended_plans[0]


def _reject_remaining_active_subscriptions(
    state: SimulationState,
    subscriber_id: str,
) -> None:
    """Reject post-states where the cancelled subscriber still has actives.

    A valid cancellation post-state has no active plan or feature
    subscriptions for the cancelled subscriber: every active
    subscription the subscriber owned at cancellation time must have
    been ended by the state-change action.
    """
    remaining = [
        s for s in state.subscriptions
        if s.subscriber_id == subscriber_id
        and s.subscription_status == ACTIVE_SUBSCRIPTION_STATUS
    ]
    if remaining:
        raise InvalidRequestError(
            f"Subscriber {subscriber_id} still has {len(remaining)} "
            "active subscription(s) in the post-cancellation state",
            violations=(
                ("active_subscription_count", len(remaining)),
            ),
        )
