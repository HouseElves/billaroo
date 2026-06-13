"""Lifecycle semantic intents and the cancellation chain (D38, D39).

A semantic action in this module applies one already-decided business
transition to a :class:`SimulationState` and returns an
:class:`ActionResult` carrying the updated state and any lifecycle
events produced.  The behaviour model chooses the transition, the
intent records the chosen transition, and the chain executor runs the
ordered consequences.

For cancellation, the chain has exactly two ordered actions (D39):

1. :class:`_ApplyCancellationStateChangeAction` atomically deactivates
   the subscriber and ends every active plan and feature subscription
   belonging to that subscriber.  It emits no lifecycle events.
2. :class:`_EmitCancellationEventAction` constructs the
   ``subscriber_cancelled`` :class:`LifecycleEvent` from the
   post-cancellation state.  It does not change state.

Both action classes are private — the public API is the action chain
returned by :func:`build_cancel_subscriber_action_chain`.
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
from synthetic_billing.actions.action_protocols import (
    ActionResult,
    SemanticAction,
)
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.lifecycle_model import (
    _find_subscriber_by_id_or_raise,
    build_subscriber_cancelled_event,
)
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = [
    "CancelSubscriberIntent",
    "build_cancel_subscriber_action_chain",
]


# ---------------------------------------------------------------------------
# Intent contract (introduced in Slice 1; behaviour unchanged in Slice 2)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# State-transformation helpers
# ---------------------------------------------------------------------------


def _find_unique_active_subscriber(
    state: SimulationState,
    subscriber_id: str,
) -> Subscriber:
    """Return the named subscriber, requiring presence and active status.

    Subscriber-ID uniqueness inside ``SimulationState`` is enforced by
    state validation; this helper trusts that invariant and only
    checks presence (via the shared lookup) and the ``active`` flag.
    """
    subscriber = _find_subscriber_by_id_or_raise(state, subscriber_id)
    if not subscriber.active:
        raise InvalidRequestError(
            f"Subscriber {subscriber_id} is already inactive",
            violations=(("active", subscriber.active),),
        )
    return subscriber


def _active_subscriptions_of(
    state: SimulationState,
    subscriber_id: str,
) -> tuple[Subscription, ...]:
    """Return all active subscriptions belonging to *subscriber_id*."""
    return tuple(
        s for s in state.subscriptions
        if s.subscriber_id == subscriber_id
        and s.subscription_status == ACTIVE_SUBSCRIPTION_STATUS
    )


def _validate_active_plan(
    active_subs: tuple[Subscription, ...],
    subscriber: Subscriber,
) -> None:
    """Require exactly one active plan that matches the subscriber's plan code."""
    plans = [s for s in active_subs if s.item_type == PLAN_ITEM_TYPE]
    if len(plans) != 1:
        raise InvalidRequestError(
            "Subscriber must have exactly one active plan subscription "
            f"at cancellation time; found {len(plans)}",
            violations=(("active_plan_count", len(plans)),),
        )
    plan = plans[0]
    if plan.item_code != subscriber.plan_code:
        raise InvalidRequestError(
            "Active plan subscription item_code disagrees with "
            "subscriber.plan_code",
            violations=(
                ("plan_code", subscriber.plan_code),
                ("item_code", plan.item_code),
            ),
        )


def _validate_start_months_before(
    active_subs: tuple[Subscription, ...],
    simulation_month: int,
) -> None:
    """Require every active subscription to have started before the month.

    Per D39 half-open semantics ``[start_month, end_month)``, a
    subscription that starts in month ``m`` and ends in month ``m``
    has an empty effective range.  Same-month start and cancellation
    is therefore unsupported and fails loudly here.
    """
    offending = [
        s for s in active_subs if s.start_month >= simulation_month
    ]
    if offending:
        raise InvalidRequestError(
            f"Same-month subscription start and cancellation in month "
            f"{simulation_month} is unsupported",
            violations=tuple(
                ("start_month", s.start_month) for s in offending
            ),
        )


def _deactivate_subscriber(
    subscribers: tuple[Subscriber, ...],
    subscriber_id: str,
) -> tuple[Subscriber, ...]:
    """Return a new subscriber tuple with the named subscriber inactive.

    Order is preserved.  ``plan_code`` is retained verbatim — the
    cancelled subscriber keeps its last assigned plan (D39).
    """
    return tuple(
        dataclasses.replace(s, active=False)
        if s.subscriber_id == subscriber_id
        else s
        for s in subscribers
    )


def _end_active_subscriptions(
    subscriptions: tuple[Subscription, ...],
    subscriber_id: str,
    simulation_month: int,
) -> tuple[Subscription, ...]:
    """Return a new subscription tuple with the subscriber's active ones ended.

    Already-ended subscriptions are preserved exactly as they are.
    Order is preserved.  Each ended subscription gets
    ``end_month == simulation_month`` and ``subscription_status ==
    "ended"`` (D39).
    """
    return tuple(
        dataclasses.replace(
            s,
            end_month=simulation_month,
            subscription_status=ENDED_SUBSCRIPTION_STATUS,
        )
        if (
            s.subscriber_id == subscriber_id
            and s.subscription_status == ACTIVE_SUBSCRIPTION_STATUS
        )
        else s
        for s in subscriptions
    )


def _apply_cancellation_to_state(
    state: SimulationState,
    intent: CancelSubscriberIntent,
) -> SimulationState:
    """Return the post-cancellation simulation state.

    Validation runs before any state is rebuilt; the input ``state``
    object and its records are never mutated (frozen dataclasses make
    that physically impossible, and the helpers above all return new
    tuples).
    """
    subscriber = _find_unique_active_subscriber(state, intent.subscriber_id)
    active_subs = _active_subscriptions_of(state, intent.subscriber_id)
    _validate_active_plan(active_subs, subscriber)
    _validate_start_months_before(active_subs, intent.simulation_month)

    new_subscribers = _deactivate_subscriber(
        state.subscribers, intent.subscriber_id,
    )
    new_subscriptions = _end_active_subscriptions(
        state.subscriptions, intent.subscriber_id, intent.simulation_month,
    )
    return SimulationState.create_validated(
        state.accounts, new_subscribers, new_subscriptions,
    )


# ---------------------------------------------------------------------------
# Private cancellation actions (D39)
# ---------------------------------------------------------------------------


# Private cancellation actions hold only the intent; their job is one
# call to ``apply``.  R0903 (too-few-public-methods) is by design here
# — additional methods would predeclare capability that no concrete
# action requires (constitution rule 22, D38).
@dataclasses.dataclass(frozen=True)
class _ApplyCancellationStateChangeAction:  # pylint: disable=too-few-public-methods
    """Atomically apply the cancellation state transition.

    Emits no lifecycle events; the audit fact is the responsibility of
    the next action in the chain.
    """

    intent: CancelSubscriberIntent

    def apply(self, state: SimulationState) -> ActionResult:
        """Return an ActionResult with the post-cancellation state and no events."""
        new_state = _apply_cancellation_to_state(state, self.intent)
        return ActionResult.create_validated(new_state, ())


@dataclasses.dataclass(frozen=True)
class _EmitCancellationEventAction:  # pylint: disable=too-few-public-methods
    """Emit the ``subscriber_cancelled`` lifecycle event.

    Operates on the post-cancellation state produced by the preceding
    state-change action; does not modify state.
    """

    intent: CancelSubscriberIntent

    def apply(self, state: SimulationState) -> ActionResult:
        """Return an ActionResult with the same state and exactly one event."""
        event = build_subscriber_cancelled_event(state, self.intent)
        return ActionResult.create_validated(state, (event,))


# ---------------------------------------------------------------------------
# Public chain builder
# ---------------------------------------------------------------------------


def build_cancel_subscriber_action_chain(
    intent: CancelSubscriberIntent,
) -> tuple[SemanticAction, ...]:
    """Build the ordered cancellation action chain (D39).

    The returned tuple has exactly two actions in this order:

    1. atomically update subscriber and subscription state;
    2. emit the cancellation lifecycle event.

    Both actions receive the same intent.  ``intent`` itself is not
    inspected here — the actions handle their own validation when
    applied.
    """
    return (
        _ApplyCancellationStateChangeAction(intent),
        _EmitCancellationEventAction(intent),
    )
