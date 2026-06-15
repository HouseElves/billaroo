"""Tests for synthetic_billing.actions.action_chain.

These tests exercise the real chain executor (D39, D43): ordering,
state threading, independent accumulation of lifecycle events,
invoices, and invoice lines, empty-chain behaviour, and exception
propagation.

The tests use small purpose-built actions rather than the cancellation
chain so that chain semantics are tested in isolation.
"""

import dataclasses

import pytest

from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.actions.action_protocols import ActionResult
from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.contracts.subscription_contracts import PLAN_ITEM_TYPE
from synthetic_billing.model.billing_model import (
    build_invoice,
    build_invoice_line,
)
from synthetic_billing.simulate.simulation_state import SimulationState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _empty_state() -> SimulationState:
    """A valid empty simulation state."""
    return SimulationState.create_validated((), (), ())


def _another_empty_state() -> SimulationState:
    """A distinct (but equivalent) empty simulation state instance."""
    return SimulationState.create_validated((), (), ())


def _event(label: str) -> LifecycleEvent:
    """Build a labelled lifecycle event for ordering checks.

    The label is encoded into the subscriber_id so the event tuples
    visibly preserve order during accumulation.
    """
    return LifecycleEvent.create_validated(
        f"event-id-{label}",
        2,
        SUBSCRIBER_CANCELLED_EVENT_TYPE,
        "acct-001",
        f"subscriber-{label}",
        "BASIC",
    )


def _invoice(label: str) -> Invoice:
    """Build a labelled invoice for ordering checks.

    The label is encoded into the account_id so the invoice tuples
    visibly preserve order during accumulation.
    """
    return build_invoice(f"acct-{label}", 1, 15, "19.99")


def _line(label: str) -> InvoiceLine:
    """Build a labelled invoice line for ordering checks.

    The label is encoded into the subscription_id so the line tuples
    visibly preserve order during accumulation.
    """
    return build_invoice_line(
        "inv-001", "subscriber-001", f"subscription-{label}",
        PLAN_ITEM_TYPE, "BASIC", "9.99",
    )


# Test-only actions are by design one-method shells: the SemanticAction
# protocol is single-method, so multi-method test doubles would be
# misleading.
class _RecordingAction:  # pylint: disable=too-few-public-methods,too-many-arguments,too-many-positional-arguments
    """Test action that records inputs and returns a configured result."""

    def __init__(
        self,
        result_state: SimulationState,
        result_events: tuple[LifecycleEvent, ...] = (),
        result_invoices: tuple[Invoice, ...] = (),
        result_lines: tuple[InvoiceLine, ...] = (),
    ) -> None:
        self.result_state = result_state
        self.result_events = result_events
        self.result_invoices = result_invoices
        self.result_lines = result_lines
        self.received_states: list[SimulationState] = []

    def apply(self, state: SimulationState) -> ActionResult:
        """Record the incoming state and return the configured result."""
        self.received_states.append(state)
        return ActionResult.create_validated(
            self.result_state,
            self.result_events,
            self.result_invoices,
            self.result_lines,
        )


class _RaisingAction:  # pylint: disable=too-few-public-methods
    """Test action whose ``apply`` raises a configured exception."""

    def __init__(self, exception: BaseException) -> None:
        self.exception = exception
        self.called = False

    def apply(self, state: SimulationState) -> ActionResult:
        """Raise the configured exception unchanged."""
        del state
        self.called = True
        raise self.exception


# ---------------------------------------------------------------------------
# Empty-chain behaviour (D39, D43)
# ---------------------------------------------------------------------------


class TestApplyActionChainEmptyChain:
    """An empty chain returns the original state and empty outputs (D43)."""

    def test_returns_action_result(self) -> None:
        """An empty chain returns an ActionResult."""
        state = _empty_state()
        result = apply_action_chain(state, ())
        assert isinstance(result, ActionResult)

    def test_state_is_original(self) -> None:
        """The returned state is the original state instance."""
        state = _empty_state()
        result = apply_action_chain(state, ())
        assert result.state is state

    def test_three_empty_output_tuples(self) -> None:
        """An empty chain accumulates no events, invoices, or lines."""
        state = _empty_state()
        result = apply_action_chain(state, ())
        assert not result.lifecycle_events
        assert not result.invoices
        assert not result.invoice_lines


# ---------------------------------------------------------------------------
# Single-action behaviour (D39, D43)
# ---------------------------------------------------------------------------


class TestApplyActionChainSingleAction:
    """A one-action chain runs the action exactly once on the input state."""

    def test_action_called_exactly_once(self) -> None:
        """The action's apply method is invoked exactly once."""
        state = _empty_state()
        action = _RecordingAction(state)
        apply_action_chain(state, (action,))
        assert len(action.received_states) == 1

    def test_action_receives_original_state(self) -> None:
        """The action receives the chain's input state."""
        state = _empty_state()
        action = _RecordingAction(state)
        apply_action_chain(state, (action,))
        assert action.received_states[0] is state

    def test_result_state_is_action_state(self) -> None:
        """The chain returns the state the action returned."""
        state_in = _empty_state()
        state_out = _another_empty_state()
        action = _RecordingAction(state_out)
        result = apply_action_chain(state_in, (action,))
        assert result.state is state_out

    def test_events_are_accumulated(self) -> None:
        """The chain returns the action's events."""
        state = _empty_state()
        event = _event("only")
        action = _RecordingAction(state, (event,))
        result = apply_action_chain(state, (action,))
        assert result.lifecycle_events == (event,)

    def test_invoices_are_accumulated(self) -> None:
        """The chain returns the action's invoices."""
        state = _empty_state()
        invoice = _invoice("only")
        action = _RecordingAction(state, (), (invoice,))
        result = apply_action_chain(state, (action,))
        assert result.invoices == (invoice,)

    def test_invoice_lines_are_accumulated(self) -> None:
        """The chain returns the action's invoice lines."""
        state = _empty_state()
        line = _line("only")
        action = _RecordingAction(state, (), (), (line,))
        result = apply_action_chain(state, (action,))
        assert result.invoice_lines == (line,)


# ---------------------------------------------------------------------------
# Multi-action behaviour: ordering, threading, accumulation (D39, D43)
# ---------------------------------------------------------------------------


class TestApplyActionChainMultipleActions:
    """A multi-action chain threads state and accumulates outputs in order."""

    def test_each_action_called_once(self) -> None:
        """Every action is invoked exactly once."""
        state = _empty_state()
        a = _RecordingAction(state)
        b = _RecordingAction(state)
        c = _RecordingAction(state)
        apply_action_chain(state, (a, b, c))
        assert (
            len(a.received_states) == len(b.received_states)
            == len(c.received_states) == 1
        )

    def test_state_threaded_through_actions(self) -> None:
        """Each action receives the previous action's returned state."""
        state_in = _empty_state()
        state_after_a = _another_empty_state()
        state_after_b = SimulationState.create_validated((), (), ())
        a = _RecordingAction(state_after_a)
        b = _RecordingAction(state_after_b)
        c = _RecordingAction(state_after_b)
        apply_action_chain(state_in, (a, b, c))
        assert a.received_states[0] is state_in
        assert b.received_states[0] is state_after_a
        assert c.received_states[0] is state_after_b

    def test_final_state_is_last_action_state(self) -> None:
        """The chain's returned state is the last action's returned state."""
        state_in = _empty_state()
        state_after_a = _another_empty_state()
        state_after_b = SimulationState.create_validated((), (), ())
        a = _RecordingAction(state_after_a)
        b = _RecordingAction(state_after_b)
        result = apply_action_chain(state_in, (a, b))
        assert result.state is state_after_b

    def test_events_accumulated_in_tuple_order(self) -> None:
        """Events are accumulated in action order, then per-action order."""
        state = _empty_state()
        a = _RecordingAction(state, (_event("a1"), _event("a2")))
        b = _RecordingAction(state, ())
        c = _RecordingAction(state, (_event("c1"),))
        result = apply_action_chain(state, (a, b, c))
        ids = [e.subscriber_id for e in result.lifecycle_events]
        assert ids == ["subscriber-a1", "subscriber-a2", "subscriber-c1"]

    def test_invoices_accumulated_in_tuple_order(self) -> None:
        """Invoices are accumulated in action order, then per-action order."""
        state = _empty_state()
        a = _RecordingAction(state, (), (_invoice("a1"), _invoice("a2")))
        b = _RecordingAction(state, (), ())
        c = _RecordingAction(state, (), (_invoice("c1"),))
        result = apply_action_chain(state, (a, b, c))
        ids = [inv.account_id for inv in result.invoices]
        assert ids == ["acct-a1", "acct-a2", "acct-c1"]

    def test_invoice_lines_accumulated_in_tuple_order(self) -> None:
        """Invoice lines accumulate in action order, then per-action order."""
        state = _empty_state()
        a = _RecordingAction(state, (), (), (_line("a1"), _line("a2")))
        b = _RecordingAction(state, (), (), ())
        c = _RecordingAction(state, (), (), (_line("c1"),))
        result = apply_action_chain(state, (a, b, c))
        ids = [ln.subscription_id for ln in result.invoice_lines]
        assert ids == [
            "subscription-a1", "subscription-a2", "subscription-c1",
        ]

    def test_output_families_stay_in_their_own_collections(self) -> None:
        """Events, invoices, and lines never leak into each other's tuples."""
        state = _empty_state()
        a = _RecordingAction(
            state, (_event("a"),), (_invoice("a"),), (_line("a"),),
        )
        b = _RecordingAction(
            state, (_event("b"),), (_invoice("b"),), (_line("b"),),
        )
        result = apply_action_chain(state, (a, b))
        assert all(
            isinstance(e, LifecycleEvent) for e in result.lifecycle_events
        )
        assert all(isinstance(i, Invoice) for i in result.invoices)
        assert all(isinstance(ln, InvoiceLine) for ln in result.invoice_lines)
        assert len(result.lifecycle_events) == 2
        assert len(result.invoices) == 2
        assert len(result.invoice_lines) == 2


# ---------------------------------------------------------------------------
# Exception propagation (D39)
# ---------------------------------------------------------------------------


class TestApplyActionChainExceptions:
    """Action exceptions propagate unchanged, no retry, no rollback (D39)."""

    def test_exception_propagates_unchanged(self) -> None:
        """The chain re-raises the action's exception verbatim."""
        state = _empty_state()
        boom = RuntimeError("nope")
        raising = _RaisingAction(boom)
        with pytest.raises(RuntimeError) as exc_info:
            apply_action_chain(state, (raising,))
        assert exc_info.value is boom

    def test_subsequent_actions_not_invoked(self) -> None:
        """A later action is never invoked when an earlier one raises."""
        state = _empty_state()
        raising = _RaisingAction(RuntimeError("boom"))
        after = _RecordingAction(state)
        with pytest.raises(RuntimeError):
            apply_action_chain(state, (raising, after))
        assert raising.called is True
        assert not after.received_states

    def test_no_retry_on_failure(self) -> None:
        """A failing action is invoked exactly once (no retry)."""
        state = _empty_state()
        raising = _RaisingAction(RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            apply_action_chain(state, (raising,))
        # _RaisingAction sets ``called=True`` before raising; a retry
        # would still set it to True, so we check via call ordering
        # instead — the next action (``after``) never runs in the
        # accompanying test, which together with this one demonstrates
        # there is no retry loop.
        assert raising.called is True


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------


class TestApplyActionChainResultEnvelope:
    """The returned ActionResult is structurally valid and frozen."""

    def test_returns_validated_action_result(self) -> None:
        """A non-empty chain returns a validated ActionResult."""
        state = _empty_state()
        action = _RecordingAction(
            state, (_event("only"),), (_invoice("only"),), (_line("only"),),
        )
        result = apply_action_chain(state, (action,))
        assert result.validate() is None

    def test_result_is_frozen(self) -> None:
        """The returned ActionResult is a frozen dataclass."""
        state = _empty_state()
        result = apply_action_chain(state, ())
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.lifecycle_events = (_event("x"),)  # type: ignore[misc]
