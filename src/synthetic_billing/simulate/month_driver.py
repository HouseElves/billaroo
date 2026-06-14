"""Monthly simulation driver (D40).

:func:`run_monthly_simulation` advances the starter-population state
through simulation months ``2 .. config.months``, selecting
cancellation intents at the start of each month and applying them in
stable order.  Lifecycle events are accumulated month-major and in
subscriber order within each month; the final
:class:`SimulationResult` carries the post-simulation state and the
ordered event log.

The driver does not draw randomness or apply chains itself.  It
delegates:

* :func:`behavior_model.choose_cancellation_intents` selects intents
  from the month-start state, drawing exactly once per active
  subscriber;
* :func:`actions.lifecycle_actions.build_cancel_subscriber_action_chain`
  expands each intent into an ordered action chain;
* :func:`actions.action_chain.apply_action_chain` applies each chain
  and returns the threaded state and emitted events.

A one-month scenario performs no transitions: the loop range is
``range(2, config.months + 1)``, which is empty when
``config.months == 1``.
"""

from __future__ import annotations

from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.actions.lifecycle_actions import (
    build_cancel_subscriber_action_chain,
)
from synthetic_billing.contracts.event_contracts import LifecycleEvent
from synthetic_billing.simulate.behavior_model import (
    choose_cancellation_intents,
    validate_cancellation_only_scope,
)
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig
from synthetic_billing.simulate.simulation_result import SimulationResult
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = ["run_monthly_simulation"]


def run_monthly_simulation(
    starter_state: SimulationState,
    config: ScenarioConfig,
    rng: RandomStream,
) -> SimulationResult:
    """Run the monthly simulation over ``starter_state`` and return the result.

    Iterates ``simulation_month`` from ``2`` through ``config.months``
    inclusive.  For each month:

    1. Snapshot the current state as the month-start state.
    2. Choose cancellation intents from that snapshot (one draw per
       active subscriber in stable order).
    3. Apply each cancellation chain in selection order, threading
       state and accumulating lifecycle events.

    The starter-population state is treated as month 1 by convention;
    a scenario with ``months == 1`` returns the starter state and an
    empty event tuple.

    Configuration is checked up front: any non-cancellation monthly
    behaviour that is configured non-zero (or any optional coherency
    group that is configured at all) fails loudly before the loop
    begins.

    Args:
        starter_state: The validated post-construction starter
            population.
        config: Scenario configuration; ``months`` and ``prob_cancel``
            drive the loop.
        rng: Caller-supplied seeded random stream.  The same stream is
            used for every monthly draw, so its position evolves
            deterministically across the run.

    Returns:
        A validated :class:`SimulationResult` carrying the final state
        and the ordered lifecycle events.
    """
    validate_cancellation_only_scope(config)

    current_state: SimulationState = starter_state
    accumulated_events: tuple[LifecycleEvent, ...] = ()

    for simulation_month in range(2, config.months + 1):
        # Capture the month-start state for selection so intermediate
        # within-month mutations cannot influence draws.
        month_start_state = current_state
        intents = choose_cancellation_intents(
            month_start_state, config, rng, simulation_month,
        )
        for intent in intents:
            chain = build_cancel_subscriber_action_chain(intent)
            step = apply_action_chain(current_state, chain)
            current_state = step.state
            accumulated_events = accumulated_events + step.lifecycle_events

    return SimulationResult.create_validated(
        current_state, accumulated_events,
    )
