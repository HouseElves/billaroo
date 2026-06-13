"""Semantic action protocol and ordered-chain result contract.

This module defines the minimum vocabulary the action layer needs in
this slice (D38):

* :class:`SemanticAction` — the structural protocol every semantic
  action satisfies.  An action applies to a :class:`SimulationState`
  and produces an :class:`ActionResult`.  The protocol is intentionally
  not runtime-checkable; concrete actions are introduced (and matched)
  by import and call site, not by isinstance.
* :class:`ActionResult` — the frozen, validated record returned by an
  applied action or an applied action chain.  It carries only the
  updated simulation state and the lifecycle events produced.

No hidden-truth, invoice, payment, log, or generic record collections
live here; constitution rule 22 (and D38) requires those abstractions
to earn their existence under real implementation pressure.
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar, Protocol

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
from synthetic_billing.contracts.event_contracts import LifecycleEvent
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = [
    "ActionResult",
    "SemanticAction",
]


@dataclasses.dataclass(frozen=True)
class ActionResult(_Validated):
    """The result of applying a semantic action or an action chain.

    Attributes:
        state: The updated simulation state after the action is applied.
        lifecycle_events: Lifecycle events the action produced, in
            emission order.  Empty when the action produced no events.
    """

    state: SimulationState
    lifecycle_events: tuple[LifecycleEvent, ...]

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("state", SimulationState),
        ("lifecycle_events", tuple),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this action result.

        Top-level field types are re-checked here so that
        direct-construction instances (which bypass
        :meth:`create_validated` and therefore the constructor type
        checks) are reported as invalid rather than silently passing.
        Per constitution rule 23, per-element checks are skipped only
        when iterating would be unsafe — i.e. when ``lifecycle_events``
        is not a tuple at all.  Correctly-typed fields still surface
        their own violations.
        """
        checks: list[CheckTuple] = [
            (
                isinstance(self.state, SimulationState),
                "state",
                self.state,
            ),
            (
                isinstance(self.lifecycle_events, tuple),
                "lifecycle_events",
                self.lifecycle_events,
            ),
        ]

        events = (
            self.lifecycle_events
            if isinstance(self.lifecycle_events, tuple)
            else ()
        )
        for index, event in enumerate(events):
            checks.append(
                (
                    isinstance(event, LifecycleEvent),
                    f"lifecycle_events[{index}]",
                    event,
                )
            )

        return tuple(checks)


# A semantic action is, by design, a single-method protocol: the
# whole point of the abstraction is that ``apply(state)`` is the only
# externally observable contract.  Additional methods would predeclare
# capability that no concrete action requires yet (constitution rule
# 22, D38).
class SemanticAction(Protocol):  # pylint: disable=too-few-public-methods
    """Structural protocol every semantic action satisfies.

    A semantic action applies one step of an already-selected business
    transition to a :class:`SimulationState` and returns an
    :class:`ActionResult` carrying the updated state and any lifecycle
    events produced by that step.  The action does not choose
    subscriber behaviour: the behaviour model chooses the transition,
    an intent records the chosen transition, and an ordered action
    chain applies its consequences one action at a time
    (``docs/action_chain_model.rst``).

    The protocol is intentionally not runtime-checkable: concrete
    actions are matched at import and call sites, not by isinstance
    (D38, constitution rule 22).
    """

    def apply(self, state: SimulationState) -> ActionResult:
        """Apply this action to ``state`` and return an ``ActionResult``."""
