"""Subscriber behaviour selection (D40).

This module owns the stochastic question: which subscribers' lives
change this month?  Slice 3 supports cancellation as the only monthly
transition, so the public surface is two functions:

* :func:`choose_cancellation_intents` — for each subscriber active at
  the start of the month, in stable :attr:`SimulationState.subscribers`
  order, draw once from the caller-supplied :class:`RandomStream` and
  build a :class:`CancelSubscriberIntent` when the draw is below
  ``ScenarioConfig.prob_cancel``.
* :func:`validate_cancellation_only_scope` — fail loudly when the
  configuration enables a monthly behaviour this slice does not
  implement (upgrade, downgrade, reactivation, feature removal,
  payment failure, the price-increase coherency group, the billing
  defect coherency group).  ``prob_feature_add`` is permitted because
  it belongs to starter-population construction (D33).

The selection function makes exactly one draw per eligible
subscriber, regardless of ``prob_cancel``, so that the RandomStream
position advances deterministically as a function of the eligible
subscriber count alone.
"""

from __future__ import annotations

from synthetic_billing.actions.lifecycle_actions import CancelSubscriberIntent
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = [
    "choose_cancellation_intents",
    "validate_cancellation_only_scope",
]


# Monthly behaviour probabilities this slice does not implement.
# ``prob_feature_add`` is intentionally absent: it governs starter
# population construction, not monthly transitions, so it is allowed
# to be non-zero even when monthly simulation only supports
# cancellation.
_UNSUPPORTED_PROBABILITY_FIELDS: tuple[str, ...] = (
    "prob_upgrade",
    "prob_downgrade",
    "prob_feature_remove",
    "prob_reactivate",
    "prob_payment_failure",
)

# Coherency-group fields whose presence indicates an unsupported
# scenario knob set is configured.  Each coherency group is all-or-
# nothing in ``ScenarioConfig``, so a single representative field is
# enough to detect the group's presence.
_UNSUPPORTED_COHERENCY_REPRESENTATIVES: tuple[str, ...] = (
    "price_increase_month",
    "duplicate_invoice_line_month",
)


def choose_cancellation_intents(
    state: SimulationState,
    config: ScenarioConfig,
    rng: RandomStream,
    simulation_month: int,
) -> tuple[CancelSubscriberIntent, ...]:
    """Select cancellation intents for a single simulation month.

    Walks :attr:`SimulationState.subscribers` in stable order.  For
    each subscriber currently active, draws one float from ``rng``;
    when the draw is below ``config.prob_cancel`` the subscriber is
    selected for cancellation in ``simulation_month``.  Inactive
    subscribers are skipped without drawing.

    Selection runs against the month-start state passed in: the
    caller is responsible for not feeding partially-applied
    intra-month state back in.

    Args:
        state: Month-start simulation state.
        config: Scenario configuration; ``prob_cancel`` governs
            selection.
        rng: Caller-supplied seeded random stream.
        simulation_month: The month the intents will be applied in.

    Returns:
        A possibly-empty tuple of :class:`CancelSubscriberIntent`,
        in the same stable order as the selected subscribers.
    """
    intents: list[CancelSubscriberIntent] = []
    for subscriber in state.subscribers:
        if not subscriber.active:
            continue
        draw = rng.random()
        if draw < config.prob_cancel:
            intents.append(
                CancelSubscriberIntent.create_validated(
                    simulation_month, subscriber.subscriber_id,
                )
            )
    return tuple(intents)


def validate_cancellation_only_scope(config: ScenarioConfig) -> None:
    """Reject configurations that enable unsupported monthly behaviour.

    Slice 3 supports cancellation as the only monthly transition.
    A non-zero probability for any other monthly behaviour, or any
    configured scenario coherency group, is treated as a
    silently-ignored knob and rejected loudly.

    Args:
        config: Scenario configuration to check.

    Raises:
        InvalidRequestError: When any unsupported monthly behaviour
            is configured.
    """
    violations: list[tuple[str, object]] = []
    for field_name in _UNSUPPORTED_PROBABILITY_FIELDS:
        value = getattr(config, field_name)
        if value != 0:
            violations.append((field_name, value))
    for field_name in _UNSUPPORTED_COHERENCY_REPRESENTATIVES:
        value = getattr(config, field_name)
        if value is not None:
            violations.append((field_name, value))
    if violations:
        raise InvalidRequestError(
            "Slice 3 supports only cancellation; the following monthly "
            "behaviour knobs are configured but unsupported",
            violations=tuple(violations),
        )
