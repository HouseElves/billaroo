"""Tests for synthetic_billing.simulate.month_driver."""

import pytest

from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.simulate.month_driver import run_monthly_simulation
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig
from synthetic_billing.simulate.simulation_result import SimulationResult
from synthetic_billing.simulate.simulation_state import SimulationState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _config(**overrides) -> ScenarioConfig:
    """Build a cancellation-only ScenarioConfig with sane defaults."""
    fields: dict[str, object] = {
        "seed": 31, "months": 3, "starting_accounts": 4,
        "prob_cancel": 0.5, "prob_feature_add": 0.0,
        "prob_upgrade": 0.0, "prob_downgrade": 0.0,
        "prob_feature_remove": 0.0, "prob_reactivate": 0.0,
        "prob_payment_failure": 0.0,
    }
    fields.update(overrides)
    return ScenarioConfig(**fields)  # type: ignore[arg-type]


def _starter_state(account_count: int = 4) -> SimulationState:
    """Build a starter-population-shaped state with N active subscribers."""
    accounts = tuple(
        Account.create_validated(
            f"acct-{i:03d}", i, 15, "US-WEST", "active",
        )
        for i in range(account_count)
    )
    subscribers = tuple(
        Subscriber.create_validated(
            f"sub-{i:03d}", f"acct-{i:03d}", 0, "BASIC", True,
        )
        for i in range(account_count)
    )
    subscriptions = tuple(
        Subscription.create_validated(
            f"pls-{i:03d}", f"sub-{i:03d}", PLAN_ITEM_TYPE, "BASIC",
            1, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        for i in range(account_count)
    )
    return SimulationState.create_validated(
        accounts, subscribers, subscriptions,
    )


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------


class TestRunMonthlySimulationResultEnvelope:
    """run_monthly_simulation returns a validated SimulationResult."""

    def test_returns_simulation_result(self) -> None:
        """The driver returns a SimulationResult."""
        config = _config(prob_cancel=0.0)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed),
        )
        assert isinstance(result, SimulationResult)

    def test_returned_result_is_validated(self) -> None:
        """The returned SimulationResult passes its own validate()."""
        config = _config(prob_cancel=0.5)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed),
        )
        assert result.validate() is None


# ---------------------------------------------------------------------------
# months == 1 corner case
# ---------------------------------------------------------------------------


class TestRunMonthlySimulationMonthsOne:
    """A scenario with months==1 performs no transitions."""

    def test_no_events_emitted(self) -> None:
        """months == 1 produces an empty event tuple."""
        config = _config(months=1, prob_cancel=1.0)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed),
        )
        assert not result.lifecycle_events

    def test_state_unchanged(self) -> None:
        """months == 1 returns the starter state untouched."""
        starter = _starter_state()
        config = _config(months=1, prob_cancel=1.0)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed),
        )
        assert result.state is starter

    def test_no_rng_draws_consumed(self) -> None:
        """months == 1 consumes zero RNG draws."""
        rng = RandomStream(7)
        config = _config(months=1, prob_cancel=1.0)
        run_monthly_simulation(_starter_state(), config, rng)
        # Compare rng position to a fresh stream of the same seed.
        assert rng.random() == RandomStream(7).random()


# ---------------------------------------------------------------------------
# Determinism + event ordering
# ---------------------------------------------------------------------------


class TestRunMonthlySimulationDeterminism:
    """Same seed + same state yields byte-identical event log."""

    def test_repeatable_event_log(self) -> None:
        """Two runs with the same inputs produce the same events."""
        config = _config(prob_cancel=0.5, months=4)
        first = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed),
        )
        second = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed),
        )
        assert first.lifecycle_events == second.lifecycle_events

    def test_repeatable_final_state(self) -> None:
        """Two runs with the same inputs produce the same final state."""
        config = _config(prob_cancel=0.5, months=4)
        first = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed),
        )
        second = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed),
        )
        assert first.state.subscribers == second.state.subscribers
        assert first.state.subscriptions == second.state.subscriptions


class TestRunMonthlySimulationEventOrdering:
    """Events are month-major and stable-subscriber-order within month."""

    def test_events_in_non_decreasing_month_order(self) -> None:
        """Event simulation_month values never decrease across the log."""
        config = _config(prob_cancel=0.5, months=6, starting_accounts=8)
        result = run_monthly_simulation(
            _starter_state(8), config, RandomStream(config.seed),
        )
        months = [e.simulation_month for e in result.lifecycle_events]
        assert months == sorted(months)

    def test_within_month_subscriber_order_preserved(self) -> None:
        """Events within one month follow stable subscriber order.

        With prob_cancel=1.0 every subscriber cancels in month 2, so
        the event log's subscriber_id order in month 2 must match
        the starter state's subscriber order exactly.
        """
        starter = _starter_state(4)
        config = _config(prob_cancel=1.0, months=2, starting_accounts=4)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed),
        )
        month_two_events = [
            e for e in result.lifecycle_events if e.simulation_month == 2
        ]
        assert [e.subscriber_id for e in month_two_events] == [
            s.subscriber_id for s in starter.subscribers
        ]


# ---------------------------------------------------------------------------
# Behavioural correctness: cancellation produces expected end state
# ---------------------------------------------------------------------------


class TestRunMonthlySimulationCancellation:
    """Cancellation produces the expected end state and events."""

    def test_certain_cancellation_deactivates_everyone(self) -> None:
        """prob_cancel = 1.0 leaves no active subscribers."""
        config = _config(prob_cancel=1.0, months=2, starting_accounts=4)
        result = run_monthly_simulation(
            _starter_state(4), config, RandomStream(config.seed),
        )
        assert all(not s.active for s in result.state.subscribers)
        assert all(
            s.subscription_status == ENDED_SUBSCRIPTION_STATUS
            for s in result.state.subscriptions
        )

    def test_zero_cancellation_preserves_state(self) -> None:
        """prob_cancel = 0.0 leaves all subscribers active and no events."""
        starter = _starter_state()
        config = _config(prob_cancel=0.0, months=6)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed),
        )
        assert not result.lifecycle_events
        assert all(s.active for s in result.state.subscribers)
        # Subscriptions stay in their starter active form.
        for sub in result.state.subscriptions:
            assert sub.subscription_status == ACTIVE_SUBSCRIPTION_STATUS
            assert sub.end_month is None

    def test_event_count_matches_inactive_subscriber_count(self) -> None:
        """Cancelled subscribers == number of subscriber_cancelled events."""
        config = _config(prob_cancel=0.5, months=8, starting_accounts=10)
        result = run_monthly_simulation(
            _starter_state(10), config, RandomStream(config.seed),
        )
        inactive = sum(1 for s in result.state.subscribers if not s.active)
        cancel_events = sum(
            1 for e in result.lifecycle_events
            if e.event_type == SUBSCRIBER_CANCELLED_EVENT_TYPE
        )
        assert inactive == cancel_events

    def test_no_subscriber_cancelled_twice(self) -> None:
        """A subscriber cancelled in month m gets no later events."""
        config = _config(prob_cancel=0.7, months=12, starting_accounts=12)
        result = run_monthly_simulation(
            _starter_state(12), config, RandomStream(config.seed),
        )
        cancelled_ids = [e.subscriber_id for e in result.lifecycle_events]
        assert len(cancelled_ids) == len(set(cancelled_ids))

    def test_event_account_id_matches_subscriber_account(self) -> None:
        """Each event's account_id matches the subscriber's owning account."""
        starter = _starter_state(6)
        config = _config(prob_cancel=1.0, months=2, starting_accounts=6)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed),
        )
        account_of = {
            s.subscriber_id: s.account_id for s in starter.subscribers
        }
        for event in result.lifecycle_events:
            assert event.account_id == account_of[event.subscriber_id]

    def test_all_events_are_subscriber_cancelled(self) -> None:
        """The only event type emitted in this slice is subscriber_cancelled."""
        config = _config(prob_cancel=0.5, months=6, starting_accounts=6)
        result = run_monthly_simulation(
            _starter_state(6), config, RandomStream(config.seed),
        )
        for event in result.lifecycle_events:
            assert event.event_type == SUBSCRIBER_CANCELLED_EVENT_TYPE
            assert isinstance(event, LifecycleEvent)


# ---------------------------------------------------------------------------
# Month-start intent selection
# ---------------------------------------------------------------------------


class TestRunMonthlySimulationMonthStartSelection:
    """Cancellation intents are chosen from each month's starting state.

    With prob_cancel=1.0 and 4 starter subscribers running across 2 months,
    every subscriber active at the start of month 2 must cancel in month 2.
    Subscribers cancelled in month 2 are inactive at the start of any
    subsequent month and consequently get no later events.
    """

    def test_all_cancellations_happen_in_first_active_month(self) -> None:
        """With prob_cancel=1.0, the second active month has nothing to draw."""
        config = _config(prob_cancel=1.0, months=4, starting_accounts=3)
        result = run_monthly_simulation(
            _starter_state(3), config, RandomStream(config.seed),
        )
        months = {e.simulation_month for e in result.lifecycle_events}
        assert months == {2}

    def test_event_per_subscriber_at_most_once(self) -> None:
        """Across the run, a subscriber is cancelled at most once.

        Month-start selection skips inactive subscribers, so a
        subscriber cancelled in month 2 cannot appear in a month-3
        event log.
        """
        config = _config(prob_cancel=1.0, months=6, starting_accounts=5)
        result = run_monthly_simulation(
            _starter_state(5), config, RandomStream(config.seed),
        )
        ids = [e.subscriber_id for e in result.lifecycle_events]
        assert sorted(ids) == sorted(set(ids))


# ---------------------------------------------------------------------------
# Input state immutability
# ---------------------------------------------------------------------------


class TestRunMonthlySimulationInputImmutability:
    """Input state and its records are never mutated by the driver."""

    def test_input_state_subscribers_unchanged(self) -> None:
        """Starter state's subscriber active flags survive the run."""
        starter = _starter_state(5)
        snapshot_active = tuple(s.active for s in starter.subscribers)
        config = _config(prob_cancel=1.0, months=3)
        run_monthly_simulation(starter, config, RandomStream(config.seed))
        assert tuple(s.active for s in starter.subscribers) == snapshot_active
        assert all(starter.subscribers[i].active for i in range(5))

    def test_input_state_subscriptions_unchanged(self) -> None:
        """Starter state's subscription end_month/status survive the run."""
        starter = _starter_state(5)
        end_months_before = tuple(s.end_month for s in starter.subscriptions)
        statuses_before = tuple(
            s.subscription_status for s in starter.subscriptions
        )
        config = _config(prob_cancel=1.0, months=3)
        run_monthly_simulation(starter, config, RandomStream(config.seed))
        assert (
            tuple(s.end_month for s in starter.subscriptions)
            == end_months_before
        )
        assert (
            tuple(s.subscription_status for s in starter.subscriptions)
            == statuses_before
        )


# ---------------------------------------------------------------------------
# Fail-loud on unsupported configuration
# ---------------------------------------------------------------------------


class TestRunMonthlySimulationUnsupportedConfig:
    """The driver fails loudly on unsupported monthly behaviour configs."""

    @pytest.mark.parametrize(
        "field_name",
        (
            "prob_upgrade",
            "prob_downgrade",
            "prob_feature_remove",
            "prob_reactivate",
            "prob_payment_failure",
        ),
    )
    def test_unsupported_probability_rejected(
        self, field_name: str,
    ) -> None:
        """A non-zero unsupported monthly probability is rejected."""
        config = _config(**{field_name: 0.1})
        with pytest.raises(InvalidRequestError):
            run_monthly_simulation(
                _starter_state(), config, RandomStream(config.seed),
            )

    def test_unsupported_check_runs_before_any_simulation(self) -> None:
        """No RNG draws are consumed when the config is rejected."""
        config = _config(prob_upgrade=0.1)
        rng = RandomStream(7)
        with pytest.raises(InvalidRequestError):
            run_monthly_simulation(_starter_state(), config, rng)
        # RNG should be untouched.
        assert rng.random() == RandomStream(7).random()
