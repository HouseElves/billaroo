"""Tests for population_builder.py.

Validates deterministic population generation, structural invariants,
and stochastic feature-subscription behavior (D33).
"""

from __future__ import annotations

from synthetic_billing.contracts.subscription_contracts import (
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
)
from synthetic_billing.model.catalog_model import (
    build_catalog,
    build_default_catalog,
    build_feature,
    build_plan,
)
from synthetic_billing.simulate.population_builder import build_population
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig


# ---- test helpers ----

def _make_config(
    seed: int = 42,
    starting_accounts: int = 5,
    prob_feature_add: float = 0.5,
    **overrides,
) -> ScenarioConfig:
    """Build a minimal ScenarioConfig for population tests."""
    defaults = {
        "seed": seed,
        "months": 12,
        "starting_accounts": starting_accounts,
        "prob_cancel": 0.0,
        "prob_upgrade": 0.0,
        "prob_downgrade": 0.0,
        "prob_feature_add": prob_feature_add,
        "prob_feature_remove": 0.0,
        "prob_reactivate": 0.0,
        "prob_payment_failure": 0.0,
    }
    defaults.update(overrides)
    return ScenarioConfig(**defaults)


def _rng_for(config: ScenarioConfig) -> RandomStream:
    """Construct the canonical RandomStream for a config (seed → stream)."""
    return RandomStream(config.seed)


# ---- determinism tests ----

class TestPopulationDeterminism:
    """Same config + same catalog → identical SimulationState (D2)."""

    def test_same_seed_same_population(self) -> None:
        """Two runs with the same seed produce identical populations."""
        config = _make_config(seed=123)
        catalog = build_default_catalog()
        state1 = build_population(config, catalog, _rng_for(config))
        state2 = build_population(config, catalog, _rng_for(config))
        assert state1 == state2

    def test_account_ids_stable(self) -> None:
        """Account IDs are identical across repeated runs."""
        config = _make_config(seed=99)
        catalog = build_default_catalog()
        ids1 = [a.account_id for a in build_population(config, catalog, _rng_for(config)).accounts]
        ids2 = [a.account_id for a in build_population(config, catalog, _rng_for(config)).accounts]
        assert ids1 == ids2

    def test_subscriber_ids_stable(self) -> None:
        """Subscriber IDs are identical across repeated runs."""
        config = _make_config(seed=99)
        catalog = build_default_catalog()
        ids1 = [
            s.subscriber_id
            for s in build_population(config, catalog, _rng_for(config)).subscribers
        ]
        ids2 = [
            s.subscriber_id
            for s in build_population(config, catalog, _rng_for(config)).subscribers
        ]
        assert ids1 == ids2

    def test_subscription_ids_stable(self) -> None:
        """Subscription IDs are identical across repeated runs."""
        config = _make_config(seed=99)
        catalog = build_default_catalog()
        ids1 = [
            s.subscription_id
            for s in build_population(config, catalog, _rng_for(config)).subscriptions
        ]
        ids2 = [
            s.subscription_id
            for s in build_population(config, catalog, _rng_for(config)).subscriptions
        ]
        assert ids1 == ids2

    def test_different_seed_different_population(self) -> None:
        """Different seeds produce different plan assignments."""
        catalog = build_default_catalog()
        state_a = build_population(_make_config(seed=1), catalog, RandomStream(1))
        state_b = build_population(_make_config(seed=2), catalog, RandomStream(2))
        plans_a = [s.plan_code for s in state_a.subscribers]
        plans_b = [s.plan_code for s in state_b.subscribers]
        # With 5 accounts and 3 plans, different seeds should usually
        # produce at least one different assignment.
        assert plans_a != plans_b


# ---- structural invariant tests ----

class TestPopulationStructure:
    """Structural invariants of the starter population."""

    def test_account_count(self) -> None:
        """Number of accounts matches config.starting_accounts."""
        config = _make_config(starting_accounts=7)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        assert len(state.accounts) == 7

    def test_one_subscriber_per_account(self) -> None:
        """Each account has exactly one subscriber."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        assert len(state.subscribers) == 5

    def test_subscriber_account_linkage(self) -> None:
        """Every subscriber's account_id matches an account."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        account_ids = {a.account_id for a in state.accounts}
        for sub in state.subscribers:
            assert sub.account_id in account_ids

    def test_subscription_subscriber_linkage(self) -> None:
        """Every subscription's subscriber_id matches a subscriber."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        subscriber_ids = {s.subscriber_id for s in state.subscribers}
        for sub in state.subscriptions:
            assert sub.subscriber_id in subscriber_ids

    def test_every_subscriber_has_plan_subscription(self) -> None:
        """Every subscriber has at least one plan subscription."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        plan_subs_by_subscriber = {
            s.subscriber_id
            for s in state.subscriptions
            if s.item_type == PLAN_ITEM_TYPE
        }
        for sub in state.subscribers:
            assert sub.subscriber_id in plan_subs_by_subscriber

    def test_plan_subscription_matches_subscriber_plan(self) -> None:
        """Each plan subscription's item_code matches the subscriber's plan."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        plan_by_subscriber = {
            s.subscriber_id: s.plan_code for s in state.subscribers
        }
        for sub in state.subscriptions:
            if sub.item_type == PLAN_ITEM_TYPE:
                assert sub.item_code == plan_by_subscriber[sub.subscriber_id]

    def test_all_subscriptions_active(self) -> None:
        """All starter subscriptions are active."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        for sub in state.subscriptions:
            assert sub.subscription_status == "active"
            assert sub.end_month is None

    def test_all_subscriptions_start_month_one(self) -> None:
        """All starter subscriptions start in month 1."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        for sub in state.subscriptions:
            assert sub.start_month == 1

    def test_all_accounts_active(self) -> None:
        """All starter accounts are active."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        for acct in state.accounts:
            assert acct.account_status == "active"

    def test_all_subscribers_active(self) -> None:
        """All starter subscribers are active."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        for sub in state.subscribers:
            assert sub.active is True

    def test_account_ordinals_sequential(self) -> None:
        """Account ordinals are 0..n-1."""
        config = _make_config(starting_accounts=5)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        ordinals = [a.account_ordinal for a in state.accounts]
        assert ordinals == list(range(5))

    def test_region_round_robin(self) -> None:
        """Regions cycle through the static vocabulary."""
        config = _make_config(starting_accounts=8)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        regions = [a.region_code for a in state.accounts]
        expected = [
            "US-WEST", "US-EAST", "US-CENTRAL", "US-SOUTH",
            "US-WEST", "US-EAST", "US-CENTRAL", "US-SOUTH",
        ]
        assert regions == expected

    def test_unique_account_ids(self) -> None:
        """All account IDs are unique."""
        config = _make_config(starting_accounts=10)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        ids = [a.account_id for a in state.accounts]
        assert len(ids) == len(set(ids))

    def test_unique_subscriber_ids(self) -> None:
        """All subscriber IDs are unique."""
        config = _make_config(starting_accounts=10)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        ids = [s.subscriber_id for s in state.subscribers]
        assert len(ids) == len(set(ids))

    def test_unique_subscription_ids(self) -> None:
        """All subscription IDs are unique."""
        config = _make_config(starting_accounts=10)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        ids = [s.subscription_id for s in state.subscriptions]
        assert len(ids) == len(set(ids))

    def test_single_account(self) -> None:
        """A population with one account is valid."""
        config = _make_config(starting_accounts=1)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        assert len(state.accounts) == 1
        assert state.is_valid()


# ---- feature subscription tests ----

class TestPopulationFeatureSubscriptions:
    """Optional feature subscription behavior."""

    def test_prob_zero_no_features(self) -> None:
        """prob_feature_add=0 produces no feature subscriptions."""
        config = _make_config(
            starting_accounts=20, prob_feature_add=0.0,
        )
        state = build_population(config, build_default_catalog(), _rng_for(config))
        feature_subs = [
            s for s in state.subscriptions
            if s.item_type == FEATURE_ITEM_TYPE
        ]
        assert len(feature_subs) == 0

    def test_prob_one_all_features(self) -> None:
        """prob_feature_add=1.0 gives every subscriber a feature subscription."""
        config = _make_config(
            starting_accounts=10, prob_feature_add=1.0,
        )
        state = build_population(config, build_default_catalog(), _rng_for(config))
        feature_subs = [
            s for s in state.subscriptions
            if s.item_type == FEATURE_ITEM_TYPE
        ]
        assert len(feature_subs) == 10

    def test_feature_plan_compatibility(self) -> None:
        """Feature subscriptions are compatible with the subscriber's plan."""
        config = _make_config(
            starting_accounts=20, prob_feature_add=1.0,
        )
        catalog = build_default_catalog()
        state = build_population(config, catalog, _rng_for(config))
        plan_by_sub = {
            s.subscriber_id: s.plan_code for s in state.subscribers
        }
        feature_defs = {f.feature_code: f for f in catalog.features}
        for sub in state.subscriptions:
            if sub.item_type == FEATURE_ITEM_TYPE:
                plan_code = plan_by_sub[sub.subscriber_id]
                feature_def = feature_defs[sub.item_code]
                assert plan_code in feature_def.allowed_plan_codes

    def test_at_most_one_feature_per_subscriber(self) -> None:
        """Each subscriber gets at most one feature subscription."""
        config = _make_config(
            starting_accounts=20, prob_feature_add=1.0,
        )
        state = build_population(config, build_default_catalog(), _rng_for(config))
        feature_counts: dict[str, int] = {}
        for sub in state.subscriptions:
            if sub.item_type == FEATURE_ITEM_TYPE:
                feature_counts[sub.subscriber_id] = (
                    feature_counts.get(sub.subscriber_id, 0) + 1
                )
        for count in feature_counts.values():
            assert count <= 1

    def test_no_features_in_catalog(self) -> None:
        """A catalog with no features produces no feature subscriptions."""
        catalog = build_catalog(
            [build_plan("SOLO", "Solo Plan", "39.99")], [],
        )
        config = _make_config(
            starting_accounts=5, prob_feature_add=1.0,
        )
        state = build_population(config, catalog, _rng_for(config))
        feature_subs = [
            s for s in state.subscriptions
            if s.item_type == FEATURE_ITEM_TYPE
        ]
        assert len(feature_subs) == 0

    def test_no_compatible_features(self) -> None:
        """Subscribers on a plan with no compatible features get none.

        Builds a catalog where ``FEAT_X`` is only compatible with
        ``PLAN_B``.  Asserts directly that every subscriber landing on
        ``PLAN_A`` receives zero feature subscriptions, and that the
        test population actually contains at least one ``PLAN_A``
        subscriber (otherwise the assertion is vacuous).
        """
        plan_a = build_plan("PLAN_A", "Plan A", "29.99")
        plan_b = build_plan("PLAN_B", "Plan B", "49.99")
        # Feature only compatible with PLAN_B.
        feat = build_feature(
            "FEAT_X", "Feature X", "9.99", ("PLAN_B",),
        )
        catalog = build_catalog([plan_a, plan_b], [feat])
        config = _make_config(
            starting_accounts=50, prob_feature_add=1.0, seed=42,
        )
        state = build_population(config, catalog, _rng_for(config))

        plan_a_subscriber_ids = {
            s.subscriber_id
            for s in state.subscribers
            if s.plan_code == "PLAN_A"
        }
        # Guard: this assertion would be vacuous if no subscribers
        # landed on PLAN_A.  Seed=42 and 50 accounts make a non-empty
        # set effectively certain with two plans.
        assert plan_a_subscriber_ids, (
            "test setup degenerate: no PLAN_A subscribers in population"
        )

        feature_subscriber_ids = {
            s.subscriber_id
            for s in state.subscriptions
            if s.item_type == FEATURE_ITEM_TYPE
        }
        # Direct claim: no PLAN_A subscriber has any feature subscription.
        assert plan_a_subscriber_ids.isdisjoint(feature_subscriber_ids)

    def test_partial_feature_add_probability(self) -> None:
        """Intermediate prob_feature_add produces a mix of with/without features."""
        config = _make_config(
            starting_accounts=100, prob_feature_add=0.5, seed=42,
        )
        state = build_population(config, build_default_catalog(), _rng_for(config))
        feature_subs = [
            s for s in state.subscriptions
            if s.item_type == FEATURE_ITEM_TYPE
        ]
        # With 100 accounts and p=0.5, we expect roughly 50 features.
        # Deterministic with seed=42, so the exact count is stable.
        assert 0 < len(feature_subs) < 100


# ---- catalog integration tests ----

class TestPopulationCatalogIntegration:
    """Population builder uses the catalog correctly."""

    def test_subscriber_plans_from_catalog(self) -> None:
        """All subscriber plan codes are drawn from the catalog."""
        catalog = build_default_catalog()
        config = _make_config(starting_accounts=20)
        state = build_population(config, catalog, _rng_for(config))
        valid_plans = {p.plan_code for p in catalog.plans}
        for sub in state.subscribers:
            assert sub.plan_code in valid_plans

    def test_single_plan_catalog(self) -> None:
        """A catalog with one plan assigns that plan to every subscriber."""
        catalog = build_catalog(
            [build_plan("ONLY", "Only Plan", "19.99")], [],
        )
        config = _make_config(starting_accounts=5)
        state = build_population(config, catalog, _rng_for(config))
        for sub in state.subscribers:
            assert sub.plan_code == "ONLY"

    def test_simulation_state_is_valid(self) -> None:
        """The produced SimulationState passes its own structural validation."""
        config = _make_config(starting_accounts=10, prob_feature_add=1.0)
        state = build_population(config, build_default_catalog(), _rng_for(config))
        assert state.is_valid()
