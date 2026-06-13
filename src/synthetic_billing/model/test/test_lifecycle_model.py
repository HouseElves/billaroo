"""Tests for synthetic_billing.model.lifecycle_model.

Slice 2 replaces the Slice 1 stub-assertion tests with tests that
exercise the real ``build_subscriber_cancelled_event`` builder (D39):
deterministic event identity, field derivation from post-cancellation
state, and fail-loud rejection of states that do not unambiguously
prove the cancellation occurred.
"""

import pytest

from synthetic_billing.actions.lifecycle_actions import (
    CancelSubscriberIntent,
    build_cancel_subscriber_action_chain,
)
from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.lifecycle_model import (
    build_subscriber_cancelled_event,
)
from synthetic_billing.simulate.simulation_state import SimulationState


# ---------------------------------------------------------------------------
# Fixture builders — post-cancellation state, focused
# ---------------------------------------------------------------------------


def _account(account_id: str = "acct-001") -> Account:
    return Account.create_validated(account_id, 0, 15, "US-WEST", "active")


def _inactive_subscriber(
    subscriber_id: str = "sub-001",
    account_id: str = "acct-001",
    plan_code: str = "BASIC",
) -> Subscriber:
    """Inactive subscriber retaining a plan_code (the post-cancellation form)."""
    return Subscriber.create_validated(
        subscriber_id, account_id, 0, plan_code, False,
    )


def _ended_plan(
    subscription_id: str = "pls-001",
    subscriber_id: str = "sub-001",
    plan_code: str = "BASIC",
    start_month: int = 1,
    end_month: int = 3,
) -> Subscription:
    """Plan subscription ended at the cancellation month."""
    return Subscription.create_validated(
        subscription_id, subscriber_id, PLAN_ITEM_TYPE, plan_code,
        start_month, end_month, ENDED_SUBSCRIPTION_STATUS,
    )


def _ended_feature(
    subscription_id: str = "fts-001",
    subscriber_id: str = "sub-001",
    feature_code: str = "HD",
    start_month: int = 1,
    end_month: int = 3,
) -> Subscription:
    """Feature subscription ended at the cancellation month."""
    return Subscription.create_validated(
        subscription_id, subscriber_id, FEATURE_ITEM_TYPE, feature_code,
        start_month, end_month, ENDED_SUBSCRIPTION_STATUS,
    )


def _post_cancellation_state() -> SimulationState:
    """State as it should look after a successful cancellation in month 3."""
    return SimulationState.create_validated(
        (_account(),),
        (_inactive_subscriber(),),
        (_ended_plan(), _ended_feature()),
    )


# ---------------------------------------------------------------------------
# Happy path: event identity and field derivation (D39)
# ---------------------------------------------------------------------------


class TestBuildSubscriberCancelledEventHappyPath:
    """Valid post-cancellation state yields a canonical lifecycle event."""

    def test_returns_lifecycle_event(self) -> None:
        """The builder returns a validated LifecycleEvent."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        event = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        assert isinstance(event, LifecycleEvent)
        assert event.validate() is None

    def test_event_type_is_subscriber_cancelled(self) -> None:
        """The event_type is the subscriber_cancelled vocabulary value."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        event = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        assert event.event_type == SUBSCRIBER_CANCELLED_EVENT_TYPE

    def test_event_id_matches_derive_id(self) -> None:
        """The event_id matches the canonical derive_id field order (D38)."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        event = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        expected = derive_id(
            "lifecycle_event",
            "subscriber_cancelled",
            "sub-001",
            3,
        )
        assert event.event_id == expected

    def test_event_carries_account_id(self) -> None:
        """The event's account_id comes from the subscriber's account."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        event = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        assert event.account_id == "acct-001"

    def test_event_carries_subscriber_id_from_intent(self) -> None:
        """The event's subscriber_id is the intent's subscriber_id."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        event = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        assert event.subscriber_id == "sub-001"

    def test_event_carries_retained_plan_code(self) -> None:
        """The event's plan_code is the retained plan_code on the subscriber."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        event = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        assert event.plan_code == "BASIC"

    def test_event_simulation_month_matches_intent(self) -> None:
        """The event's simulation_month matches the intent month."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        event = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        assert event.simulation_month == 3

    def test_event_id_deterministic_across_calls(self) -> None:
        """Two calls with the same state and intent yield identical ids."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        first = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        second = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent,
        )
        assert first.event_id == second.event_id

    def test_different_month_yields_different_id(self) -> None:
        """A different cancellation month yields a different event_id."""
        intent_three = CancelSubscriberIntent.create_validated(3, "sub-001")
        event_three = build_subscriber_cancelled_event(
            _post_cancellation_state(), intent_three,
        )
        # Build an equivalent post-state but ending at month 4.
        state_four = SimulationState.create_validated(
            (_account(),),
            (_inactive_subscriber(),),
            (_ended_plan(end_month=4), _ended_feature(end_month=4)),
        )
        intent_four = CancelSubscriberIntent.create_validated(4, "sub-001")
        event_four = build_subscriber_cancelled_event(state_four, intent_four)
        assert event_three.event_id != event_four.event_id

    def test_chain_event_equals_direct_event(self) -> None:
        """Running the full chain emits the same event the direct builder produces."""
        # Build the pre-cancellation state (active subscriber and active subs).
        active_subscriber = Subscriber.create_validated(
            "sub-001", "acct-001", 0, "BASIC", True,
        )
        active_plan = Subscription.create_validated(
            "pls-001", "sub-001", PLAN_ITEM_TYPE, "BASIC",
            1, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        active_feature = Subscription.create_validated(
            "fts-001", "sub-001", FEATURE_ITEM_TYPE, "HD",
            1, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        pre_state = SimulationState.create_validated(
            (_account(),),
            (active_subscriber,),
            (active_plan, active_feature),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        chain_result = apply_action_chain(pre_state, chain)
        direct_event = build_subscriber_cancelled_event(
            chain_result.state, intent,
        )
        assert chain_result.lifecycle_events == (direct_event,)


# ---------------------------------------------------------------------------
# Fail-loud paths (D39)
# ---------------------------------------------------------------------------


class TestBuildSubscriberCancelledEventFailLoud:
    """Inconsistent post-state is rejected loudly (D39)."""

    def test_missing_subscriber(self) -> None:
        """A subscriber not present in state fails loudly."""
        state = _post_cancellation_state()
        intent = CancelSubscriberIntent.create_validated(3, "ghost")
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        assert any(
            f == "subscriber_id" for f, _ in exc_info.value.violations
        )

    def test_subscriber_still_active_fails(self) -> None:
        """A subscriber that is still active fails loudly."""
        still_active = Subscriber.create_validated(
            "sub-001", "acct-001", 0, "BASIC", True,
        )
        state = SimulationState.create_validated(
            (_account(),), (still_active,), (_ended_plan(),),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        assert any(f == "active" for f, _ in exc_info.value.violations)

    def test_no_plan_ended_in_intent_month(self) -> None:
        """A state with no plan ended in the intent month fails loudly."""
        state = SimulationState.create_validated(
            (_account(),),
            (_inactive_subscriber(),),
            (_ended_feature(),),  # no plan among the ended subscriptions
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        assert ("ended_plan_count", 0) in exc_info.value.violations

    def test_multiple_plans_ended_in_intent_month(self) -> None:
        """Two plan subscriptions ending in the intent month fails loudly."""
        second_plan = Subscription.create_validated(
            "pls-extra", "sub-001", PLAN_ITEM_TYPE, "BASIC",
            1, 3, ENDED_SUBSCRIPTION_STATUS,
        )
        state = SimulationState.create_validated(
            (_account(),),
            (_inactive_subscriber(),),
            (_ended_plan(), second_plan),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        assert ("ended_plan_count", 2) in exc_info.value.violations

    def test_plan_code_disagrees_with_subscriber_plan_code(self) -> None:
        """An ended plan whose item_code disagrees fails loudly."""
        subscriber = _inactive_subscriber(plan_code="PRO")
        plan = _ended_plan(plan_code="BASIC")
        state = SimulationState.create_validated(
            (_account(),), (subscriber,), (plan,),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "plan_code" in field_names
        assert "item_code" in field_names


# ---------------------------------------------------------------------------
# Cancellation-event semantic checks (D39 correction)
# ---------------------------------------------------------------------------


class TestCancellationEventSemanticChecks:
    """Builder rejects unsound post-states the existing checks would accept."""

    def test_remaining_active_feature_rejected(self) -> None:
        """A still-active feature for the cancelled subscriber fails loudly.

        Subscriber is inactive and the plan is ended, but a feature
        subscription is still active.  The chain would never produce
        this, but the event builder is the proof boundary and must
        reject it.
        """
        active_feature = Subscription.create_validated(
            "fts-001", "sub-001", FEATURE_ITEM_TYPE, "HD",
            1, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        state = SimulationState.create_validated(
            (_account(),),
            (_inactive_subscriber(),),
            (_ended_plan(), active_feature),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        assert (
            "active_subscription_count", 1,
        ) in exc_info.value.violations

    def test_matching_plan_with_empty_effective_range_rejected(self) -> None:
        """A matching ended plan with ``start_month == end_month`` fails loudly.

        For a cancellation in month ``m`` the matching plan must
        satisfy ``start_month < end_month == m``.  An empty effective
        range ``[m, m)`` is not a valid evidence record.
        """
        empty_range_plan = Subscription.create_validated(
            "pls-001", "sub-001", PLAN_ITEM_TYPE, "BASIC",
            3, 3, ENDED_SUBSCRIPTION_STATUS,
        )
        state = SimulationState.create_validated(
            (_account(),),
            (_inactive_subscriber(),),
            (empty_range_plan,),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber_cancelled_event(state, intent)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "start_month" in field_names
        assert "end_month" in field_names
