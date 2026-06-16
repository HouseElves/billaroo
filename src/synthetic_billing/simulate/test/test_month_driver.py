"""Tests for synthetic_billing.simulate.month_driver."""

from decimal import Decimal

import pytest

from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.actions.lifecycle_actions import (
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
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.catalog_model import build_default_catalog
from synthetic_billing.simulate.behavior_model import (
    choose_cancellation_intents,
)
from synthetic_billing.simulate.month_driver import run_monthly_simulation
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig
from synthetic_billing.simulate.simulation_result import SimulationResult
from synthetic_billing.simulate.simulation_state import SimulationState


# The default catalog prices the BASIC plan used by the starter-state
# fixture, so billing fixtures resolve every chargeable subscription.
_CATALOG = build_default_catalog()


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
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert isinstance(result, SimulationResult)

    def test_returned_result_is_validated(self) -> None:
        """The returned SimulationResult passes its own validate()."""
        config = _config(prob_cancel=0.5)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
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
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert not result.lifecycle_events

    def test_state_unchanged(self) -> None:
        """months == 1 returns the starter state untouched."""
        starter = _starter_state()
        config = _config(months=1, prob_cancel=1.0)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed), _CATALOG,
        )
        assert result.state is starter

    def test_no_rng_draws_consumed(self) -> None:
        """months == 1 consumes zero RNG draws."""
        rng = RandomStream(7)
        config = _config(months=1, prob_cancel=1.0)
        run_monthly_simulation(_starter_state(), config, rng, _CATALOG)
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
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        second = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert first.lifecycle_events == second.lifecycle_events

    def test_repeatable_final_state(self) -> None:
        """Two runs with the same inputs produce the same final state."""
        config = _config(prob_cancel=0.5, months=4)
        first = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        second = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert first.state.subscribers == second.state.subscribers
        assert first.state.subscriptions == second.state.subscriptions


class TestRunMonthlySimulationEventOrdering:
    """Events are month-major and stable-subscriber-order within month."""

    def test_events_in_non_decreasing_month_order(self) -> None:
        """Event simulation_month values never decrease across the log."""
        config = _config(prob_cancel=0.5, months=6, starting_accounts=8)
        result = run_monthly_simulation(
            _starter_state(8), config, RandomStream(config.seed), _CATALOG,
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
            starter, config, RandomStream(config.seed), _CATALOG,
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
            _starter_state(4), config, RandomStream(config.seed), _CATALOG,
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
            starter, config, RandomStream(config.seed), _CATALOG,
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
            _starter_state(10), config, RandomStream(config.seed), _CATALOG,
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
            _starter_state(12), config, RandomStream(config.seed), _CATALOG,
        )
        cancelled_ids = [e.subscriber_id for e in result.lifecycle_events]
        assert len(cancelled_ids) == len(set(cancelled_ids))

    def test_event_account_id_matches_subscriber_account(self) -> None:
        """Each event's account_id matches the subscriber's owning account."""
        starter = _starter_state(6)
        config = _config(prob_cancel=1.0, months=2, starting_accounts=6)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed), _CATALOG,
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
            _starter_state(6), config, RandomStream(config.seed), _CATALOG,
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
            _starter_state(3), config, RandomStream(config.seed), _CATALOG,
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
            _starter_state(5), config, RandomStream(config.seed), _CATALOG,
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
        run_monthly_simulation(starter, config, RandomStream(config.seed), _CATALOG)
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
        run_monthly_simulation(starter, config, RandomStream(config.seed), _CATALOG)
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
                _starter_state(), config, RandomStream(config.seed), _CATALOG,
            )

    def test_unsupported_check_runs_before_any_simulation(self) -> None:
        """No RNG draws are consumed when the config is rejected."""
        config = _config(prob_upgrade=0.1)
        rng = RandomStream(7)
        with pytest.raises(InvalidRequestError):
            run_monthly_simulation(_starter_state(), config, rng, _CATALOG)
        # RNG should be untouched.
        assert rng.random() == RandomStream(7).random()


# ===========================================================================
# Run-level recurring billing integration (D46)
# ===========================================================================


def _billing_config(**overrides) -> ScenarioConfig:
    """Build a billing-friendly cancellation-only config.

    Defaults to no cancellation so every starter subscriber stays
    chargeable across the horizon; individual tests override
    ``prob_cancel`` and ``months`` as needed.
    """
    base: dict[str, object] = {"prob_cancel": 0.0, "months": 3}
    base.update(overrides)
    return _config(**base)


def _account_order(state: SimulationState) -> dict[str, int]:
    """Return a map of account id to its index in the state's account order."""
    return {a.account_id: index for index, a in enumerate(state.accounts)}


def _lines_by_invoice(result: SimulationResult) -> dict[str, list]:
    """Group a result's invoice lines by their invoice id."""
    grouped: dict[str, list] = {}
    for line in result.invoice_lines:
        grouped.setdefault(line.invoice_id, []).append(line)
    return grouped


class TestRunMonthlySimulationBillingResultShape:
    """The result exposes ordered invoices and invoice lines."""

    def test_result_has_billing_collections(self) -> None:
        """The result carries invoice and invoice-line tuples."""
        config = _billing_config()
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert isinstance(result.invoices, tuple)
        assert isinstance(result.invoice_lines, tuple)

    def test_result_validates_with_billing(self) -> None:
        """A result carrying billing passes its own validate()."""
        config = _billing_config(months=4)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert result.validate() is None

    def test_billing_present_for_chargeable_population(self) -> None:
        """A chargeable starter population produces invoices."""
        config = _billing_config()
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert result.invoices
        assert result.invoice_lines


class TestRunMonthlySimulationMonthOneBilling:
    """Month 1 is billed even though it carries no transition."""

    def test_one_month_scenario_bills_month_one(self) -> None:
        """months == 1 still produces month-1 invoices."""
        config = _billing_config(months=1)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert result.invoices
        assert all(i.simulation_month == 1 for i in result.invoices)

    def test_one_month_scenario_has_no_events(self) -> None:
        """months == 1 bills but performs no lifecycle transition."""
        config = _billing_config(months=1, prob_cancel=1.0)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert not result.lifecycle_events
        assert result.invoices

    def test_one_month_one_invoice_per_account(self) -> None:
        """Every active starter account is billed exactly once in month 1."""
        starter = _starter_state(5)
        config = _billing_config(months=1, starting_accounts=5)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed), _CATALOG,
        )
        billed_accounts = [i.account_id for i in result.invoices]
        assert sorted(billed_accounts) == sorted(
            a.account_id for a in starter.accounts
        )


class TestRunMonthlySimulationMultiMonthBilling:
    """Multi-month runs bill each month the account is chargeable."""

    def test_one_invoice_per_account_per_month_no_cancellation(self) -> None:
        """With no cancellation, every account bills every month."""
        config = _billing_config(months=3, starting_accounts=4)
        result = run_monthly_simulation(
            _starter_state(4), config, RandomStream(config.seed), _CATALOG,
        )
        # 4 accounts * 3 months, all chargeable throughout.
        assert len(result.invoices) == 4 * 3

    def test_invoice_months_span_full_horizon(self) -> None:
        """Invoices cover months 1 through config.months inclusive."""
        config = _billing_config(months=5, starting_accounts=3)
        result = run_monthly_simulation(
            _starter_state(3), config, RandomStream(config.seed), _CATALOG,
        )
        billed_months = {i.simulation_month for i in result.invoices}
        assert billed_months == {1, 2, 3, 4, 5}


class TestRunMonthlySimulationCancellationAffectsBilling:
    """Lifecycle transitions for a month precede that month's billing."""

    def test_cancelled_subscription_not_charged_in_cancel_month(self) -> None:
        """Everyone cancels in month 2, so only month 1 produces invoices.

        Under the half-open ``[start_month, end_month)`` convention, a
        subscription ending in month 2 is not chargeable in month 2.
        With prob_cancel=1.0 every starter subscriber cancels in month 2,
        so no invoice appears for month 2 or later.
        """
        config = _billing_config(
            months=4, starting_accounts=6, prob_cancel=1.0,
        )
        result = run_monthly_simulation(
            _starter_state(6), config, RandomStream(config.seed), _CATALOG,
        )
        billed_months = {i.simulation_month for i in result.invoices}
        assert billed_months == {1}
        assert len(result.invoices) == 6

    def test_billing_observes_post_transition_state(self) -> None:
        """An account whose only subscriber cancels stops being billed.

        Each account has exactly one subscriber here, so a cancelled
        subscriber leaves its account with no chargeable subscription
        from the cancellation month onward.
        """
        config = _billing_config(
            months=3, starting_accounts=4, prob_cancel=1.0,
        )
        result = run_monthly_simulation(
            _starter_state(4), config, RandomStream(config.seed), _CATALOG,
        )
        # Month 1: all four billed. Months 2-3: none (all cancelled m2).
        per_month = {}
        for invoice in result.invoices:
            per_month.setdefault(invoice.simulation_month, 0)
            per_month[invoice.simulation_month] += 1
        assert per_month == {1: 4}


class TestRunMonthlySimulationBillingOrdering:
    """Billing order is month-major then state-account order within a month."""

    def test_invoices_in_non_decreasing_month_order(self) -> None:
        """Invoice simulation_month values never decrease across the run."""
        config = _billing_config(months=5, starting_accounts=4)
        result = run_monthly_simulation(
            _starter_state(4), config, RandomStream(config.seed), _CATALOG,
        )
        months = [i.simulation_month for i in result.invoices]
        assert months == sorted(months)

    def test_within_month_account_order_matches_state(self) -> None:
        """Within each billed month, invoice order follows account order."""
        starter = _starter_state(5)
        config = _billing_config(months=3, starting_accounts=5)
        result = run_monthly_simulation(
            starter, config, RandomStream(config.seed), _CATALOG,
        )
        order = _account_order(result.state)
        for month in {i.simulation_month for i in result.invoices}:
            month_indices = [
                order[i.account_id]
                for i in result.invoices
                if i.simulation_month == month
            ]
            assert month_indices == sorted(month_indices)


class TestRunMonthlySimulationBillingInvariants:
    """The result satisfies the required billing invariants."""

    def test_at_most_one_invoice_per_account_month(self) -> None:
        """No (account, month) pair is billed twice."""
        config = _billing_config(months=4, starting_accounts=5, prob_cancel=0.3)
        result = run_monthly_simulation(
            _starter_state(5), config, RandomStream(config.seed), _CATALOG,
        )
        keys = [(i.account_id, i.simulation_month) for i in result.invoices]
        assert len(keys) == len(set(keys))

    def test_each_invoice_one_account_one_month(self) -> None:
        """Each invoice names exactly one account and one month."""
        config = _billing_config(months=3, starting_accounts=4)
        result = run_monthly_simulation(
            _starter_state(4), config, RandomStream(config.seed), _CATALOG,
        )
        for invoice in result.invoices:
            assert isinstance(invoice.account_id, str)
            assert invoice.simulation_month >= 1

    def test_every_line_references_a_run_invoice(self) -> None:
        """Each invoice line's invoice_id is one returned by the run."""
        config = _billing_config(months=4, starting_accounts=5, prob_cancel=0.3)
        result = run_monthly_simulation(
            _starter_state(5), config, RandomStream(config.seed), _CATALOG,
        )
        invoice_ids = {i.invoice_id for i in result.invoices}
        assert all(
            line.invoice_id in invoice_ids for line in result.invoice_lines
        )

    def test_invoice_total_equals_sum_of_its_lines(self) -> None:
        """Each invoice total reconciles against its own lines."""
        config = _billing_config(months=4, starting_accounts=5, prob_cancel=0.3)
        result = run_monthly_simulation(
            _starter_state(5), config, RandomStream(config.seed), _CATALOG,
        )
        grouped = _lines_by_invoice(result)
        for invoice in result.invoices:
            line_sum = sum(
                (line.line_amount for line in grouped.get(invoice.invoice_id, [])),
                Decimal("0"),
            )
            assert invoice.total_amount == line_sum

    def test_every_invoice_has_at_least_one_line(self) -> None:
        """A returned invoice always has lines (empty invoices are not emitted)."""
        config = _billing_config(months=3, starting_accounts=4)
        result = run_monthly_simulation(
            _starter_state(4), config, RandomStream(config.seed), _CATALOG,
        )
        grouped = _lines_by_invoice(result)
        for invoice in result.invoices:
            assert grouped.get(invoice.invoice_id)

    def test_billing_emits_no_lifecycle_events(self) -> None:
        """Billing contributes no lifecycle events of its own.

        With no cancellation configured, the run produces invoices but
        an empty lifecycle-event log.
        """
        config = _billing_config(months=4, prob_cancel=0.0)
        result = run_monthly_simulation(
            _starter_state(), config, RandomStream(config.seed), _CATALOG,
        )
        assert result.invoices
        assert not result.lifecycle_events


class TestRunMonthlySimulationNothingChargeable:
    """Account-months with nothing chargeable produce no invoice."""

    def test_no_invoice_when_no_subscriptions(self) -> None:
        """An account with no subscribers/subscriptions is never billed."""
        account = Account.create_validated(
            "acct-lonely", 0, 15, "US-WEST", "active",
        )
        state = SimulationState.create_validated((account,), (), ())
        config = _billing_config(months=3, starting_accounts=1)
        result = run_monthly_simulation(
            state, config, RandomStream(config.seed), _CATALOG,
        )
        assert not result.invoices
        assert not result.invoice_lines

    def test_no_invoice_for_non_active_account(self) -> None:
        """A present non-active account produces no invoice."""
        account = Account.create_validated(
            "acct-suspended", 0, 15, "US-WEST", "suspended",
        )
        subscriber = Subscriber.create_validated(
            "sub-susp", "acct-suspended", 0, "BASIC", True,
        )
        subscription = Subscription.create_validated(
            "pls-susp", "sub-susp", PLAN_ITEM_TYPE, "BASIC",
            1, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        state = SimulationState.create_validated(
            (account,), (subscriber,), (subscription,),
        )
        config = _billing_config(months=2, starting_accounts=1)
        result = run_monthly_simulation(
            state, config, RandomStream(config.seed), _CATALOG,
        )
        assert not result.invoices

    def test_future_only_subscription_not_billed_early(self) -> None:
        """A subscription starting later is not billed before its start."""
        account = Account.create_validated(
            "acct-future", 0, 15, "US-WEST", "active",
        )
        subscriber = Subscriber.create_validated(
            "sub-future", "acct-future", 0, "BASIC", True,
        )
        subscription = Subscription.create_validated(
            "pls-future", "sub-future", PLAN_ITEM_TYPE, "BASIC",
            5, None, ACTIVE_SUBSCRIPTION_STATUS,
        )
        state = SimulationState.create_validated(
            (account,), (subscriber,), (subscription,),
        )
        config = _billing_config(months=3, starting_accounts=1)
        result = run_monthly_simulation(
            state, config, RandomStream(config.seed), _CATALOG,
        )
        # Subscription starts month 5; months 1-3 produce nothing.
        assert not result.invoices


class TestRunMonthlySimulationBillingDeterminism:
    """Repeated runs with equivalent inputs produce equivalent billing."""

    def test_repeatable_invoices(self) -> None:
        """Two runs with the same inputs produce equal invoices."""
        config = _billing_config(months=5, starting_accounts=6, prob_cancel=0.3)
        first = run_monthly_simulation(
            _starter_state(6), config, RandomStream(config.seed), _CATALOG,
        )
        second = run_monthly_simulation(
            _starter_state(6), config, RandomStream(config.seed), _CATALOG,
        )
        assert first.invoices == second.invoices

    def test_repeatable_invoice_lines(self) -> None:
        """Two runs with the same inputs produce equal invoice lines."""
        config = _billing_config(months=5, starting_accounts=6, prob_cancel=0.3)
        first = run_monthly_simulation(
            _starter_state(6), config, RandomStream(config.seed), _CATALOG,
        )
        second = run_monthly_simulation(
            _starter_state(6), config, RandomStream(config.seed), _CATALOG,
        )
        assert first.invoice_lines == second.invoice_lines


class TestRunMonthlySimulationBillingPreservesRandomness:
    """Billing does not consume or perturb the cancellation draw sequence."""

    def test_rng_position_unaffected_by_billing(self) -> None:
        """The RNG ends where a cancellation-only run would leave it.

        Billing consumes no draws, so after a run the shared stream's
        position depends only on the cancellation selection — identical
        to the position a billing-free reconstruction reaches.
        """
        config = _billing_config(months=6, starting_accounts=8, prob_cancel=0.4)

        rng_run = RandomStream(config.seed)
        run_monthly_simulation(
            _starter_state(8), config, rng_run, _CATALOG,
        )

        # Reconstruct the cancellation-only draw consumption: one draw
        # per active subscriber at each month start.
        rng_replay = RandomStream(config.seed)
        replay_state = _starter_state(8)
        for month in range(2, config.months + 1):
            intents = choose_cancellation_intents(
                replay_state, config, rng_replay, month,
            )
            for intent in intents:
                chain = build_cancel_subscriber_action_chain(intent)
                step = apply_action_chain(replay_state, chain)
                replay_state = step.state

        # Both streams must now be at the same position.
        assert rng_run.random() == rng_replay.random()

    def test_cancellation_events_unchanged_by_billing(self) -> None:
        """The lifecycle-event log matches a billing-free reconstruction."""
        config = _billing_config(months=6, starting_accounts=8, prob_cancel=0.4)

        result = run_monthly_simulation(
            _starter_state(8), config, RandomStream(config.seed), _CATALOG,
        )

        rng_replay = RandomStream(config.seed)
        replay_state = _starter_state(8)
        replay_events = ()
        for month in range(2, config.months + 1):
            intents = choose_cancellation_intents(
                replay_state, config, rng_replay, month,
            )
            for intent in intents:
                chain = build_cancel_subscriber_action_chain(intent)
                step = apply_action_chain(replay_state, chain)
                replay_state = step.state
                replay_events = replay_events + step.lifecycle_events

        assert result.lifecycle_events == replay_events
        assert result.state.subscribers == replay_state.subscribers
        assert result.state.subscriptions == replay_state.subscriptions
