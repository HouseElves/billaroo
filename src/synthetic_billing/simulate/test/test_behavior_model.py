"""Tests for synthetic_billing.simulate.behavior_model."""

import dataclasses
from decimal import Decimal

import pytest

from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.simulate.behavior_model import (
    choose_cancellation_intents,
    validate_cancellation_only_scope,
)
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig
from synthetic_billing.simulate.simulation_state import SimulationState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_BASE_CONFIG = ScenarioConfig(
    seed=17,
    months=6,
    starting_accounts=3,
    prob_cancel=0.5,
    prob_upgrade=0.0,
    prob_downgrade=0.0,
    prob_feature_add=0.0,
    prob_feature_remove=0.0,
    prob_reactivate=0.0,
    prob_payment_failure=0.0,
)


def _config(**overrides) -> ScenarioConfig:
    """Build a cancellation-only ScenarioConfig with sane defaults."""
    return dataclasses.replace(_BASE_CONFIG, **overrides)


def _account(account_id: str = "acct-001") -> Account:
    return Account.create_validated(account_id, 0, 15, "US-WEST", "active")


def _active_subscriber(
    subscriber_id: str,
    account_id: str = "acct-001",
    ordinal: int = 0,
) -> Subscriber:
    return Subscriber.create_validated(
        subscriber_id, account_id, ordinal, "BASIC", True,
    )


def _inactive_subscriber(
    subscriber_id: str,
    account_id: str = "acct-001",
    ordinal: int = 0,
) -> Subscriber:
    return Subscriber.create_validated(
        subscriber_id, account_id, ordinal, "BASIC", False,
    )


def _plan_for(subscriber_id: str, suffix: str) -> Subscription:
    return Subscription.create_validated(
        f"pls-{suffix}", subscriber_id, PLAN_ITEM_TYPE, "BASIC",
        1, None, ACTIVE_SUBSCRIPTION_STATUS,
    )


def _three_active_state() -> SimulationState:
    """State with three active subscribers in deterministic order."""
    return SimulationState.create_validated(
        (_account(),),
        (
            _active_subscriber("subscriber-a", ordinal=0),
            _active_subscriber("subscriber-b", ordinal=1),
            _active_subscriber("subscriber-c", ordinal=2),
        ),
        (
            _plan_for("subscriber-a", "a"),
            _plan_for("subscriber-b", "b"),
            _plan_for("subscriber-c", "c"),
        ),
    )


# ---------------------------------------------------------------------------
# choose_cancellation_intents (D40)
# ---------------------------------------------------------------------------


class TestChooseCancellationIntents:
    """Selection draws once per active subscriber in stable order."""

    def test_prob_zero_yields_no_intents(self) -> None:
        """With prob_cancel = 0, no subscriber is selected."""
        state = _three_active_state()
        config = _config(prob_cancel=0.0)
        rng = RandomStream(config.seed)
        assert not choose_cancellation_intents(state, config, rng, 2)

    def test_prob_one_yields_intent_per_active_subscriber(self) -> None:
        """With prob_cancel = 1, every active subscriber is selected."""
        state = _three_active_state()
        config = _config(prob_cancel=1.0)
        rng = RandomStream(config.seed)
        intents = choose_cancellation_intents(state, config, rng, 2)
        assert len(intents) == 3
        assert [i.subscriber_id for i in intents] == [
            "subscriber-a", "subscriber-b", "subscriber-c",
        ]

    def test_intents_carry_simulation_month(self) -> None:
        """Each intent carries the simulation_month it was selected in."""
        state = _three_active_state()
        config = _config(prob_cancel=1.0)
        rng = RandomStream(config.seed)
        intents = choose_cancellation_intents(state, config, rng, 5)
        assert all(i.simulation_month == 5 for i in intents)

    def test_inactive_subscribers_skipped(self) -> None:
        """Inactive subscribers are not considered for cancellation."""
        state = SimulationState.create_validated(
            (_account(),),
            (
                _active_subscriber("subscriber-a", ordinal=0),
                _inactive_subscriber("subscriber-b", ordinal=1),
                _active_subscriber("subscriber-c", ordinal=2),
            ),
            (
                _plan_for("subscriber-a", "a"),
                _plan_for("subscriber-c", "c"),
            ),
        )
        config = _config(prob_cancel=1.0)
        rng = RandomStream(config.seed)
        intents = choose_cancellation_intents(state, config, rng, 2)
        assert [i.subscriber_id for i in intents] == [
            "subscriber-a", "subscriber-c",
        ]

    def test_one_draw_per_active_subscriber(self) -> None:
        """Selection consumes exactly len(active subscribers) RNG draws.

        Compared against a parallel RandomStream that consumes that
        same number of draws, the selection's RNG must be in the same
        position afterwards.
        """
        state = _three_active_state()
        config = _config(prob_cancel=0.5)
        rng = RandomStream(config.seed)
        choose_cancellation_intents(state, config, rng, 2)
        # Three subscribers consumed three draws.
        next_draw_after_selection = rng.random()
        baseline = RandomStream(config.seed)
        for _ in range(3):
            baseline.random()
        assert next_draw_after_selection == baseline.random()

    def test_no_draws_for_inactive_subscribers(self) -> None:
        """Inactive subscribers do not consume RNG draws."""
        state_with_inactive = SimulationState.create_validated(
            (_account(),),
            (
                _active_subscriber("subscriber-a", ordinal=0),
                _inactive_subscriber("subscriber-b", ordinal=1),
                _active_subscriber("subscriber-c", ordinal=2),
            ),
            (
                _plan_for("subscriber-a", "a"),
                _plan_for("subscriber-c", "c"),
            ),
        )
        config = _config(prob_cancel=0.5)
        rng = RandomStream(config.seed)
        choose_cancellation_intents(state_with_inactive, config, rng, 2)
        # Only two draws were consumed: subscriber-a and subscriber-c.
        next_draw_after = rng.random()
        baseline = RandomStream(config.seed)
        for _ in range(2):
            baseline.random()
        assert next_draw_after == baseline.random()

    def test_stable_subscriber_order_preserved(self) -> None:
        """Intents are returned in SimulationState.subscribers order."""
        state = _three_active_state()
        config = _config(prob_cancel=1.0)
        rng = RandomStream(config.seed)
        intents = choose_cancellation_intents(state, config, rng, 2)
        assert [i.subscriber_id for i in intents] == [
            s.subscriber_id for s in state.subscribers
        ]


# ---------------------------------------------------------------------------
# validate_cancellation_only_scope (D40)
# ---------------------------------------------------------------------------


class TestValidateCancellationOnlyScope:
    """Unsupported monthly behaviour configuration fails loudly (D40)."""

    def test_cancellation_only_config_accepted(self) -> None:
        """A config with only prob_cancel non-zero passes."""
        config = _config(prob_cancel=0.1)
        assert validate_cancellation_only_scope(config) is None

    def test_prob_feature_add_does_not_fail(self) -> None:
        """prob_feature_add belongs to starter population and is permitted."""
        config = _config(prob_feature_add=0.5)
        assert validate_cancellation_only_scope(config) is None

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
        """Each unsupported monthly probability is rejected when non-zero."""
        config = _config(**{field_name: 0.1})
        with pytest.raises(InvalidRequestError) as exc_info:
            validate_cancellation_only_scope(config)
        assert any(
            f == field_name for f, _ in exc_info.value.violations
        )

    def test_price_increase_coherency_group_rejected(self) -> None:
        """A configured price-increase coherency group is rejected."""
        config = dataclasses.replace(
            _config(),
            price_increase_month=3,
            price_increase_amount=Decimal("2.50"),
            price_increase_cancel_lift=0.1,
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            validate_cancellation_only_scope(config)
        assert any(
            f == "price_increase_month"
            for f, _ in exc_info.value.violations
        )

    def test_duplicate_invoice_line_defect_rejected(self) -> None:
        """A configured billing-defect coherency group is rejected."""
        config = dataclasses.replace(
            _config(),
            duplicate_invoice_line_month=4,
            duplicate_invoice_line_probability=0.05,
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            validate_cancellation_only_scope(config)
        assert any(
            f == "duplicate_invoice_line_month"
            for f, _ in exc_info.value.violations
        )

    def test_multiple_violations_collected(self) -> None:
        """Multiple unsupported knobs surface together."""
        config = _config(prob_upgrade=0.1, prob_payment_failure=0.2)
        with pytest.raises(InvalidRequestError) as exc_info:
            validate_cancellation_only_scope(config)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "prob_upgrade" in field_names
        assert "prob_payment_failure" in field_names
