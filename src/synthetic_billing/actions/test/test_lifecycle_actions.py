"""Tests for synthetic_billing.actions.lifecycle_actions.

Slice 2 replaces the Slice 1 stub-assertion test for
``build_cancel_subscriber_action_chain`` with tests that exercise the
real two-action chain (D39).  ``CancelSubscriberIntent`` validation
tests are preserved unchanged from Slice 1.
"""

import dataclasses

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.actions.action_protocols import ActionResult
from synthetic_billing.actions.lifecycle_actions import (
    CancelSubscriberIntent,
    build_cancel_subscriber_action_chain,
)
from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.simulate.simulation_state import SimulationState


# ---------------------------------------------------------------------------
# Fixtures — explicit, small, validated
# ---------------------------------------------------------------------------


def _active_account(account_id: str = "acct-001") -> Account:
    """Build a validated active account."""
    return Account.create_validated(account_id, 0, 15, "US-WEST", "active")


def _active_subscriber(
    subscriber_id: str = "sub-001",
    account_id: str = "acct-001",
    plan_code: str = "BASIC",
) -> Subscriber:
    """Build a validated active subscriber."""
    return Subscriber.create_validated(
        subscriber_id, account_id, 0, plan_code, True,
    )


def _active_plan(
    subscription_id: str = "pls-001",
    subscriber_id: str = "sub-001",
    plan_code: str = "BASIC",
    start_month: int = 1,
) -> Subscription:
    """Build a validated active plan subscription."""
    return Subscription.create_validated(
        subscription_id, subscriber_id, PLAN_ITEM_TYPE, plan_code,
        start_month, None, ACTIVE_SUBSCRIPTION_STATUS,
    )


def _active_feature(
    subscription_id: str = "fts-001",
    subscriber_id: str = "sub-001",
    feature_code: str = "HD",
    start_month: int = 1,
) -> Subscription:
    """Build a validated active feature subscription."""
    return Subscription.create_validated(
        subscription_id, subscriber_id, FEATURE_ITEM_TYPE, feature_code,
        start_month, None, ACTIVE_SUBSCRIPTION_STATUS,
    )


def _ended_plan(
    subscription_id: str = "pls-old",
    subscriber_id: str = "sub-001",
    plan_code: str = "LITE",
    start_month: int = 1,
    end_month: int = 2,
) -> Subscription:
    """Build a validated historical (already-ended) plan subscription."""
    return Subscription.create_validated(
        subscription_id, subscriber_id, PLAN_ITEM_TYPE, plan_code,
        start_month, end_month, ENDED_SUBSCRIPTION_STATUS,
    )


def _basic_state() -> SimulationState:
    """State with one account, one active subscriber, one plan, one feature."""
    return SimulationState.create_validated(
        (_active_account(),),
        (_active_subscriber(),),
        (_active_plan(), _active_feature()),
    )


# ---------------------------------------------------------------------------
# CancelSubscriberIntent — preserved from Slice 1
# ---------------------------------------------------------------------------


class TestCancelSubscriberIntentHappyPath:
    """Valid cancellation intents construct without errors."""

    def test_valid_intent(self) -> None:
        """A valid intent for month 2 constructs cleanly."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        assert intent.simulation_month == 2
        assert intent.subscriber_id == "sub-001"

    def test_month_two_is_accepted(self) -> None:
        """simulation_month = 2 is the earliest legal cancellation month."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        assert intent.simulation_month == 2

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        with pytest.raises(dataclasses.FrozenInstanceError):
            intent.simulation_month = 3  # type: ignore[misc]


class TestCancelSubscriberIntentValidatedProtocol:
    """CancelSubscriberIntent exercises the _Validated mix-in correctly."""

    def test_is_validated_subclass(self) -> None:
        """CancelSubscriberIntent inherits from _Validated."""
        assert issubclass(CancelSubscriberIntent, _Validated)

    def test_validate_happy_path(self) -> None:
        """validate() on a valid instance returns None."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        assert intent.validate() is None

    def test_is_valid_true(self) -> None:
        """is_valid() returns True for a structurally valid instance."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        assert intent.is_valid() is True


class TestCancelSubscriberIntentTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_bool_simulation_month(self) -> None:
        """Bool simulation_month is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            CancelSubscriberIntent.create_validated(True, "sub-001")
        assert ("simulation_month", True) in exc_info.value.violations

    def test_non_int_simulation_month(self) -> None:
        """A string simulation_month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            CancelSubscriberIntent.create_validated("2", "sub-001")
        assert ("simulation_month", "2") in exc_info.value.violations

    def test_non_string_subscriber_id(self) -> None:
        """A non-string subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            CancelSubscriberIntent.create_validated(2, 42)
        assert ("subscriber_id", 42) in exc_info.value.violations


class TestCancelSubscriberIntentStructuralChecks:
    """Structural validation catches value-range and shape errors."""

    def test_month_one_rejected(self) -> None:
        """simulation_month = 1 is the starter month and is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            CancelSubscriberIntent.create_validated(1, "sub-001")
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_blank_subscriber_id(self) -> None:
        """A whitespace-only subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            CancelSubscriberIntent.create_validated(2, "   ")
        assert any(f == "subscriber_id" for f, _ in exc_info.value.violations)


# ---------------------------------------------------------------------------
# build_cancel_subscriber_action_chain — chain composition (D39)
# ---------------------------------------------------------------------------


class TestCancelSubscriberActionChainComposition:
    """The chain builder returns a frozen ordered two-action tuple (D39)."""

    def test_returns_tuple(self) -> None:
        """The result is a tuple, not a list or any iterable."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        assert isinstance(chain, tuple)

    def test_has_exactly_two_actions(self) -> None:
        """The cancellation chain has exactly two actions (D39)."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        assert len(chain) == 2

    def test_every_action_has_apply(self) -> None:
        """Every action is callable via the SemanticAction protocol."""
        intent = CancelSubscriberIntent.create_validated(2, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        for action in chain:
            assert callable(getattr(action, "apply", None))


# ---------------------------------------------------------------------------
# Action 1: state-change action — observable behaviour (D39)
# ---------------------------------------------------------------------------


class TestStateChangeAction:
    """The first action transitions state atomically with no events."""

    def test_returns_no_events(self) -> None:
        """Action 1 emits no lifecycle events."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        assert isinstance(result, ActionResult)
        assert not result.lifecycle_events

    def test_subscriber_becomes_inactive(self) -> None:
        """The named subscriber is inactive after the state-change action."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        assert result.state.subscribers[0].active is False

    def test_subscriber_retains_plan_code(self) -> None:
        """The inactive subscriber retains its last assigned plan code."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        assert result.state.subscribers[0].plan_code == "BASIC"

    def test_active_plan_subscription_ends_at_month(self) -> None:
        """The active plan subscription is ended with end_month=intent month."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        plan = result.state.subscriptions[0]
        assert plan.end_month == 3
        assert plan.subscription_status == ENDED_SUBSCRIPTION_STATUS

    def test_active_feature_subscription_ends_at_month(self) -> None:
        """Every active feature subscription is ended with end_month=intent month."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        feature = result.state.subscriptions[1]
        assert feature.end_month == 3
        assert feature.subscription_status == ENDED_SUBSCRIPTION_STATUS

    def test_already_ended_subscription_preserved(self) -> None:
        """Historical ended subscriptions are preserved exactly as they are."""
        state = SimulationState.create_validated(
            (_active_account(),),
            (_active_subscriber(),),
            (
                _ended_plan(),
                _active_plan(),
                _active_feature(),
            ),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        # The historical ended_plan is untouched.
        assert result.state.subscriptions[0] is state.subscriptions[0]

    def test_unrelated_subscriber_preserved(self) -> None:
        """Subscribers and subscriptions for other subscribers are untouched."""
        other = Subscriber.create_validated(
            "sub-002", "acct-001", 1, "BASIC", True,
        )
        other_plan = Subscription.create_validated(
            "pls-002", "sub-002", PLAN_ITEM_TYPE, "BASIC",
            1, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        state = SimulationState.create_validated(
            (_active_account(),),
            (_active_subscriber(), other),
            (_active_plan(), _active_feature(), other_plan),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        assert result.state.subscribers[1] is other
        assert result.state.subscriptions[2] is other_plan

    def test_tuple_order_preserved(self) -> None:
        """Tuple order is preserved for subscribers and subscriptions."""
        other = Subscriber.create_validated(
            "sub-002", "acct-001", 1, "BASIC", True,
        )
        state = SimulationState.create_validated(
            (_active_account(),),
            (_active_subscriber(), other),
            (_active_plan(), _active_feature()),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = chain[0].apply(state)
        ids_subs = [s.subscriber_id for s in result.state.subscribers]
        ids_subscr = [s.subscription_id for s in result.state.subscriptions]
        assert ids_subs == ["sub-001", "sub-002"]
        assert ids_subscr == ["pls-001", "fts-001"]

    def test_input_state_not_mutated(self) -> None:
        """The input state and its records remain unchanged after the action."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        chain[0].apply(state)
        assert state.subscribers[0].active is True
        assert state.subscriptions[0].end_month is None
        assert (
            state.subscriptions[0].subscription_status
            == ACTIVE_SUBSCRIPTION_STATUS
        )
        assert state.subscriptions[1].end_month is None


# ---------------------------------------------------------------------------
# Action 1 fail-loud paths (D39)
# ---------------------------------------------------------------------------


class TestStateChangeActionFailLoud:
    """Invalid inputs and inconsistent state are rejected loudly (D39)."""

    def test_missing_subscriber(self) -> None:
        """A subscriber not present in state fails loudly."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "ghost")
        chain = build_cancel_subscriber_action_chain(intent)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        assert any(
            f == "subscriber_id" for f, _ in exc_info.value.violations
        )

    def test_subscriber_already_inactive(self) -> None:
        """An already-inactive subscriber fails loudly."""
        inactive = Subscriber.create_validated(
            "sub-001", "acct-001", 0, "BASIC", False,
        )
        # No active subscriptions for an inactive subscriber.
        state = SimulationState.create_validated(
            (_active_account(),), (inactive,), (),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        assert any(f == "active" for f, _ in exc_info.value.violations)

    def test_no_active_plan_subscription(self) -> None:
        """A subscriber with no active plan subscription fails loudly."""
        state = SimulationState.create_validated(
            (_active_account(),), (_active_subscriber(),), (),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        assert ("active_plan_count", 0) in exc_info.value.violations

    def test_duplicate_active_plan_subscriptions(self) -> None:
        """Two active plan subscriptions fail loudly."""
        second_plan = Subscription.create_validated(
            "pls-extra", "sub-001", PLAN_ITEM_TYPE, "BASIC",
            1, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        state = SimulationState.create_validated(
            (_active_account(),),
            (_active_subscriber(),),
            (_active_plan(), second_plan),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        assert ("active_plan_count", 2) in exc_info.value.violations

    def test_plan_code_disagrees_with_subscriber(self) -> None:
        """A plan subscription whose item_code disagrees fails loudly."""
        subscriber = _active_subscriber(plan_code="PRO")
        plan = _active_plan(plan_code="BASIC")
        state = SimulationState.create_validated(
            (_active_account(),), (subscriber,), (plan,),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "plan_code" in field_names
        assert "item_code" in field_names

    def test_same_month_start_and_cancellation_rejected(self) -> None:
        """A subscription starting in the cancellation month fails loudly."""
        plan = _active_plan(start_month=3)
        state = SimulationState.create_validated(
            (_active_account(),),
            (_active_subscriber(),),
            (plan,),
        )
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        assert any(
            f == "start_month" for f, _ in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# Action 2: event-emit action — observable behaviour (D39)
# ---------------------------------------------------------------------------


class TestEventEmitAction:
    """The second action emits exactly one event without changing state."""

    def test_emits_exactly_one_event_on_post_state(self) -> None:
        """Action 2 applied to the post-cancellation state emits one event."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        post_state = chain[0].apply(_basic_state()).state
        emit_result = chain[1].apply(post_state)
        assert len(emit_result.lifecycle_events) == 1
        event = emit_result.lifecycle_events[0]
        assert isinstance(event, LifecycleEvent)
        assert event.event_type == SUBSCRIBER_CANCELLED_EVENT_TYPE

    def test_state_unchanged_by_event_action(self) -> None:
        """Action 2 returns the same state instance it received."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        post_state = chain[0].apply(_basic_state()).state
        emit_result = chain[1].apply(post_state)
        assert emit_result.state is post_state

    def test_event_action_on_pre_state_fails_loud(self) -> None:
        """Running the event action against the pre-state fails loudly."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        with pytest.raises(InvalidRequestError):
            chain[1].apply(_basic_state())


# ---------------------------------------------------------------------------
# End-to-end through apply_action_chain (D39)
# ---------------------------------------------------------------------------


class TestCancellationEndToEnd:
    """Apply the full cancellation chain via apply_action_chain (D39)."""

    def test_full_chain_produces_expected_state_and_event(self) -> None:
        """The chain produces a cancelled state and one canonical event."""
        state = _basic_state()
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain = build_cancel_subscriber_action_chain(intent)
        result = apply_action_chain(state, chain)
        assert len(result.lifecycle_events) == 1
        event = result.lifecycle_events[0]
        assert event.event_type == SUBSCRIBER_CANCELLED_EVENT_TYPE
        assert event.simulation_month == 3
        assert event.subscriber_id == "sub-001"
        assert event.account_id == "acct-001"
        assert event.plan_code == "BASIC"
        assert result.state.subscribers[0].active is False
        for sub in result.state.subscriptions:
            assert sub.end_month == 3
            assert sub.subscription_status == ENDED_SUBSCRIPTION_STATUS

    def test_full_chain_deterministic(self) -> None:
        """The same state + intent produces a byte-identical event id."""
        intent = CancelSubscriberIntent.create_validated(3, "sub-001")
        chain_one = build_cancel_subscriber_action_chain(intent)
        chain_two = build_cancel_subscriber_action_chain(intent)
        first = apply_action_chain(_basic_state(), chain_one)
        second = apply_action_chain(_basic_state(), chain_two)
        assert first.lifecycle_events == second.lifecycle_events
