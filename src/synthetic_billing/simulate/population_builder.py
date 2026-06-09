"""Deterministic starter population builder.

Builds an in-memory ``SimulationState`` from a ``ScenarioConfig``,
``Catalog``, and explicit ``RandomStream``.  The population is the
initial state of the simulation before any monthly transitions run.

Design decision D33 scopes this slice: the first runnable baseline
produces deterministic in-memory state only.  Raw emission, CLI, and
downstream analytics are separate slices.

All stochastic decisions flow through the caller-supplied
``RandomStream`` (D12).  The caller is responsible for constructing
``RandomStream(config.seed)``; passing the stream explicitly keeps the
builder decoupled from internal RNG construction and makes
substream/seed-injection patterns straightforward for tests.  Same
config + same catalog + same RNG seed → identical ``SimulationState``
(D2).
"""

from __future__ import annotations

from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import Subscription
from synthetic_billing.model.account_model import build_account
from synthetic_billing.model.subscriber_model import build_subscriber
from synthetic_billing.model.subscription_model import (
    build_feature_subscription,
    build_plan_subscription,
)
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = ["build_population"]

# Static population vocabulary — small and deterministic.
# Regions cycle round-robin across accounts; billing cycle days are
# chosen uniformly from a short list via the seeded stream.
_REGIONS: tuple[str, ...] = ("US-WEST", "US-EAST", "US-CENTRAL", "US-SOUTH")
_BILLING_CYCLE_DAYS: tuple[int, ...] = (1, 8, 15, 22)

# Every subscriber starts in simulation month 1.
_INITIAL_MONTH: int = 1


def build_population(
    config: ScenarioConfig,
    catalog: Catalog,
    rng: RandomStream,
) -> SimulationState:
    """Build a deterministic starter population.

    Creates ``config.starting_accounts`` accounts, one subscriber per
    account, one active plan subscription per subscriber, and optionally
    one active feature subscription per subscriber (gated by
    ``config.prob_feature_add`` and feature-plan compatibility).

    The population is fully deterministic for a given ``(config,
    catalog, rng)`` triple.  Determinism is the responsibility of the
    caller's RNG construction; passing ``RandomStream(config.seed)``
    is the canonical pattern.

    Args:
        config: Scenario configuration.
        catalog: Plan and feature catalog.
        rng: Seeded random stream for all stochastic decisions.

    Returns:
        A frozen ``SimulationState`` containing the starter population.
    """
    plan_codes = [p.plan_code for p in catalog.plans]

    accounts = []
    subscribers = []
    subscriptions = []

    for ordinal in range(config.starting_accounts):
        # --- account ---
        region = _REGIONS[ordinal % len(_REGIONS)]
        billing_day = rng.choice(_BILLING_CYCLE_DAYS)
        account = build_account(
            seed=config.seed,
            account_ordinal=ordinal,
            billing_cycle_day=billing_day,
            region_code=region,
        )
        accounts.append(account)

        # --- subscriber (one per account for v0) ---
        chosen_plan = rng.choice(plan_codes)
        subscriber = build_subscriber(
            account_id=account.account_id,
            subscriber_ordinal=0,
            plan_code=chosen_plan,
            catalog=catalog,
        )
        subscribers.append(subscriber)

        # --- plan subscription ---
        plan_sub = build_plan_subscription(
            subscriber_id=subscriber.subscriber_id,
            plan_code=chosen_plan,
            start_month=_INITIAL_MONTH,
            catalog=catalog,
        )
        subscriptions.append(plan_sub)

        # --- optional feature subscription ---
        feature_sub = _choose_feature_subscription(
            rng, config, catalog, subscriber, chosen_plan,
        )
        if feature_sub is not None:
            subscriptions.append(feature_sub)

    return SimulationState.create_validated(
        tuple(accounts),
        tuple(subscribers),
        tuple(subscriptions),
    )


def _choose_feature_subscription(
    rng: RandomStream,
    config: ScenarioConfig,
    catalog: Catalog,
    subscriber: Subscriber,
    plan_code: str,
) -> Subscription | None:
    """Optionally choose and build a feature subscription.

    Returns a ``Subscription`` if a compatible feature is chosen, or
    ``None`` if the random draw fails, no features exist, or no
    features are compatible with the subscriber's plan.
    """
    if not catalog.features:
        return None

    if rng.random() >= config.prob_feature_add:
        return None

    compatible = [
        f for f in catalog.features
        if plan_code in f.allowed_plan_codes
    ]
    if not compatible:
        return None

    chosen_feature = rng.choice(compatible)
    return build_feature_subscription(
        subscriber_id=subscriber.subscriber_id,
        feature_code=chosen_feature.feature_code,
        plan_code=plan_code,
        start_month=_INITIAL_MONTH,
        catalog=catalog,
    )
