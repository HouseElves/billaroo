"""Ordered action-chain application (D38, D39, D43).

:func:`apply_action_chain` executes a tuple of :class:`SemanticAction`
instances in order, threading state from one action's result into the
next action's input, and accumulating their lifecycle events, invoices,
and invoice lines in emission order.

It does not retry, wrap, or roll back action failures: any exception
raised by an action propagates unchanged.  Empty chains return the
original state and three empty output tuples.
"""

from __future__ import annotations

from synthetic_billing.actions.action_protocols import (
    ActionResult,
    SemanticAction,
)
from synthetic_billing.contracts.event_contracts import LifecycleEvent
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = ["apply_action_chain"]


def apply_action_chain(
    state: SimulationState,
    actions: tuple[SemanticAction, ...],
) -> ActionResult:
    """Apply an ordered action chain to ``state``.

    Each action is invoked exactly once, in tuple order, and is passed
    the state returned by the previous action.  Lifecycle events,
    invoices, and invoice lines are each accumulated independently in
    action order, preserving the order produced within each action; no
    record is deduplicated, sorted, reconciled, or reinterpreted (D43).
    Exceptions raised by any action propagate unchanged (no retry, no
    wrapping, no rollback).

    Args:
        state: The starting simulation state.
        actions: The ordered chain of semantic actions to apply.

    Returns:
        An :class:`ActionResult` carrying the final threaded state and
        the accumulated lifecycle events, invoices, and invoice lines.
        An empty chain returns ``ActionResult(state, (), (), ())``.
    """
    current_state: SimulationState = state
    accumulated_events: tuple[LifecycleEvent, ...] = ()
    accumulated_invoices: tuple[Invoice, ...] = ()
    accumulated_lines: tuple[InvoiceLine, ...] = ()
    for action in actions:
        step = action.apply(current_state)
        current_state = step.state
        accumulated_events = accumulated_events + step.lifecycle_events
        accumulated_invoices = accumulated_invoices + step.invoices
        accumulated_lines = accumulated_lines + step.invoice_lines
    return ActionResult.create_validated(
        current_state,
        accumulated_events,
        accumulated_invoices,
        accumulated_lines,
    )
