"""Ordered action-chain application entry point.

This slice fixes the public boundary of chain application (D38).  The
function ``apply_action_chain`` accepts a frozen simulation state and an
ordered tuple of semantic actions, and returns a single
:class:`ActionResult` summarising the combined effect on state and the
ordered lifecycle events produced.

Execution semantics (per-action application, event accumulation,
ordering guarantees, error handling) belong to a later slice.  This
entry point raises ``NotImplementedError`` immediately; its companion
test asserts that boundary under constitution rule 21.
"""

from __future__ import annotations

from synthetic_billing.actions.action_protocols import (
    ActionResult,
    SemanticAction,
)
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = ["apply_action_chain"]


def apply_action_chain(
    state: SimulationState,
    actions: tuple[SemanticAction, ...],
) -> ActionResult:
    """Apply an ordered action chain to ``state``.

    Application semantics — per-action invocation, lifecycle-event
    accumulation, and ordering guarantees — are reserved for a later
    slice (D38).  This entry point raises ``NotImplementedError``
    immediately and does not inspect either argument.
    """
    del state, actions
    raise NotImplementedError("apply_action_chain is not implemented")
