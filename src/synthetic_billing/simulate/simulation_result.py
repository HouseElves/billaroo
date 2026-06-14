"""Result of a complete monthly simulation run (D40).

A :class:`SimulationResult` carries the final
:class:`SimulationState` after all months have advanced, together with
every lifecycle event emitted along the way, in deterministic
emission order.

This is the simulation-level result envelope, distinct from
:class:`synthetic_billing.actions.action_protocols.ActionResult`: an
``ActionResult`` is the result of applying one semantic action or
chain to one state; a :class:`SimulationResult` is the cumulative
record of running the monthly driver over the full configured horizon.
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
from synthetic_billing.contracts.event_contracts import LifecycleEvent
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = ["SimulationResult"]


# Hoisted out of the class body so the type-spec declaration is a
# single reference rather than an inlined literal that visually mirrors
# the action-layer envelope's spec.
_RESULT_TYPE_SPECS: tuple[CheckSpec, ...] = (
    ("state", SimulationState),
    ("lifecycle_events", tuple),
)


@dataclasses.dataclass(frozen=True)
class SimulationResult(_Validated):
    """The terminal state and ordered event log of a simulation run.

    Attributes:
        state: The final :class:`SimulationState` after the last
            simulated month has been applied.
        lifecycle_events: The lifecycle events emitted during the run,
            in deterministic emission order (month-major; within each
            month in stable subscriber order).  Empty when the run
            performed no transitions.
    """

    state: SimulationState
    lifecycle_events: tuple[LifecycleEvent, ...]

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = _RESULT_TYPE_SPECS

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this result.

        Top-level field types are re-checked so that
        direct-construction instances (which bypass
        :meth:`create_validated` and therefore the constructor type
        checks) are reported as invalid rather than silently passing.
        When ``lifecycle_events`` is the wrong top-level type, the
        per-element checks are skipped — iterating it would not be a
        safely observable check (constitution rule 23).
        """
        state_typed = isinstance(self.state, SimulationState)
        events_typed = isinstance(self.lifecycle_events, tuple)
        top_level: tuple[CheckTuple, ...] = (
            (state_typed, "state", self.state),
            (events_typed, "lifecycle_events", self.lifecycle_events),
        )
        if not events_typed:
            return top_level
        per_event: tuple[CheckTuple, ...] = tuple(
            (isinstance(event, LifecycleEvent),
             f"lifecycle_events[{index}]", event)
            for index, event in enumerate(self.lifecycle_events)
        )
        return top_level + per_event
