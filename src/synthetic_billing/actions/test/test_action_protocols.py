"""Tests for synthetic_billing.actions.action_protocols."""

import dataclasses

import pytest

from synthetic_billing.actions.action_protocols import ActionResult
from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.contracts.subscription_contracts import PLAN_ITEM_TYPE
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.billing_model import (
    build_invoice,
    build_invoice_line,
)
from synthetic_billing.simulate.simulation_state import SimulationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_state() -> SimulationState:
    """Return a valid empty simulation state.

    An empty state passes structural validation: all per-element checks
    iterate over empty tuples, and uniqueness/cross-reference checks
    pass trivially over empty ID sets.
    """
    return SimulationState.create_validated((), (), ())


def _cancel_event(event_id: str = "evt-cancel-001") -> LifecycleEvent:
    """Build a valid subscriber_cancelled lifecycle event."""
    return LifecycleEvent.create_validated(
        event_id,
        2,
        SUBSCRIBER_CANCELLED_EVENT_TYPE,
        "acct-001",
        "subscriber-001",
        "BASIC",
    )


def _invoice(month: int = 1) -> Invoice:
    """Build a valid Invoice for an account-month."""
    return build_invoice("acct-001", month, 15, "19.99")


def _line(subscription_id: str = "subscription-001") -> InvoiceLine:
    """Build a valid InvoiceLine for a subscription on an invoice."""
    return build_invoice_line(
        "inv-001", "subscriber-001", subscription_id,
        PLAN_ITEM_TYPE, "BASIC", "9.99",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestActionResultHappyPath:
    """Valid ActionResult instances construct without errors."""

    def test_all_outputs_empty(self) -> None:
        """An ActionResult with all output tuples empty constructs cleanly."""
        state = _empty_state()
        result = ActionResult.create_validated(state, (), (), ())
        assert result.state is state
        assert isinstance(result.lifecycle_events, tuple)
        assert isinstance(result.invoices, tuple)
        assert isinstance(result.invoice_lines, tuple)
        assert not result.lifecycle_events
        assert not result.invoices
        assert not result.invoice_lines

    def test_single_event(self) -> None:
        """An ActionResult with one valid lifecycle event constructs."""
        state = _empty_state()
        event = _cancel_event()
        result = ActionResult.create_validated(state, (event,), (), ())
        assert result.lifecycle_events == (event,)

    def test_multiple_events(self) -> None:
        """An ActionResult with multiple valid lifecycle events constructs."""
        state = _empty_state()
        events = (_cancel_event("evt-1"), _cancel_event("evt-2"))
        result = ActionResult.create_validated(state, events, (), ())
        assert result.lifecycle_events == events

    def test_single_invoice(self) -> None:
        """An ActionResult with one valid invoice constructs."""
        state = _empty_state()
        invoice = _invoice()
        result = ActionResult.create_validated(state, (), (invoice,), ())
        assert result.invoices == (invoice,)

    def test_multiple_invoices_order_preserved(self) -> None:
        """Multiple invoices are stored in the order provided."""
        state = _empty_state()
        invoices = (_invoice(1), _invoice(2))
        result = ActionResult.create_validated(state, (), invoices, ())
        assert result.invoices == invoices

    def test_single_invoice_line(self) -> None:
        """An ActionResult with one valid invoice line constructs."""
        state = _empty_state()
        line = _line()
        result = ActionResult.create_validated(state, (), (), (line,))
        assert result.invoice_lines == (line,)

    def test_multiple_invoice_lines_order_preserved(self) -> None:
        """Multiple invoice lines are stored in the order provided."""
        state = _empty_state()
        lines = (_line("subscription-1"), _line("subscription-2"))
        result = ActionResult.create_validated(state, (), (), lines)
        assert result.invoice_lines == lines

    def test_all_collections_populated(self) -> None:
        """Events, invoices, and lines coexist in one result, each in place."""
        state = _empty_state()
        events = (_cancel_event(),)
        invoices = (_invoice(),)
        lines = (_line(),)
        result = ActionResult.create_validated(
            state, events, invoices, lines,
        )
        assert result.lifecycle_events == events
        assert result.invoices == invoices
        assert result.invoice_lines == lines

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        state = _empty_state()
        result = ActionResult.create_validated(state, (), (), ())
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.invoices = (_invoice(),)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Type-check rejections (via create_validated)
# ---------------------------------------------------------------------------


class TestActionResultTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_state_type_rejected(self) -> None:
        """A non-SimulationState state argument is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated("not a state", (), (), ())
        assert any(f == "state" for f, _ in exc_info.value.violations)

    def test_lifecycle_events_must_be_tuple(self) -> None:
        """A list passed as lifecycle_events is rejected by the type spec."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, [], (), ())
        assert any(
            f == "lifecycle_events" for f, _ in exc_info.value.violations
        )

    def test_invoices_must_be_tuple(self) -> None:
        """A list passed as invoices is rejected by the type spec."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (), [], ())
        assert any(f == "invoices" for f, _ in exc_info.value.violations)

    def test_invoice_lines_must_be_tuple(self) -> None:
        """A list passed as invoice_lines is rejected by the type spec."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (), (), [])
        assert any(
            f == "invoice_lines" for f, _ in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# Structural-check rejections (via create_validated and via validate)
# ---------------------------------------------------------------------------


class TestActionResultStructuralChecks:
    """Structural validation catches per-element and direct-construction errors."""

    def test_non_event_element_rejected(self) -> None:
        """A non-LifecycleEvent element is reported at its index."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, ("not an event",), (), ())
        assert any(
            f == "lifecycle_events[0]"
            for f, _ in exc_info.value.violations
        )

    def test_non_invoice_element_rejected(self) -> None:
        """A non-Invoice element is reported at its index."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (), ("not an invoice",), ())
        assert any(
            f == "invoices[0]" for f, _ in exc_info.value.violations
        )

    def test_non_invoice_line_element_rejected(self) -> None:
        """A non-InvoiceLine element is reported at its index."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (), (), ("not a line",))
        assert any(
            f == "invoice_lines[0]" for f, _ in exc_info.value.violations
        )

    def test_mixed_valid_and_invalid_events(self) -> None:
        """Per-element checks report only the bogus elements (rule 23)."""
        state = _empty_state()
        good = _cancel_event()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (good, "nope"), (), ())
        field_names = {f for f, _ in exc_info.value.violations}
        assert "lifecycle_events[0]" not in field_names
        assert "lifecycle_events[1]" in field_names

    def test_mixed_valid_and_invalid_invoices(self) -> None:
        """Invoice per-element checks report only the bogus elements."""
        state = _empty_state()
        good = _invoice()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (), (good, "nope"), ())
        field_names = {f for f, _ in exc_info.value.violations}
        assert "invoices[0]" not in field_names
        assert "invoices[1]" in field_names

    def test_mixed_valid_and_invalid_invoice_lines(self) -> None:
        """Invoice-line per-element checks report only the bogus elements."""
        state = _empty_state()
        good = _line()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (), (), (good, "nope"))
        field_names = {f for f, _ in exc_info.value.violations}
        assert "invoice_lines[0]" not in field_names
        assert "invoice_lines[1]" in field_names

    def test_direct_construction_state_surfaced(self) -> None:
        """Direct construction with a bogus state surfaces a state violation.

        Direct construction bypasses create_validated and its constructor
        type checks; the structural re-check ensures the violation is
        still observable (rule 23).
        """
        result = ActionResult(
            state="not a state",  # type: ignore[arg-type]
            lifecycle_events=(),
            invoices=(),
            invoice_lines=(),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        assert any(f == "state" for f, _ in exc_info.value.violations)

    def test_non_tuple_collection_skips_only_its_elements(self) -> None:
        """A non-tuple collection surfaces its own violation only (rule 23).

        ``invoices`` is not a tuple, so its per-element checks are
        skipped, but the well-typed ``lifecycle_events`` tuple still has
        its bogus element reported.
        """
        state = _empty_state()
        result = ActionResult(
            state=state,
            lifecycle_events=("nope",),  # type: ignore[arg-type]
            invoices=["not a tuple"],  # type: ignore[arg-type]
            invoice_lines=(),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        field_names = {f for f, _ in exc_info.value.violations}
        assert "invoices" in field_names
        assert "invoices[0]" not in field_names
        assert "lifecycle_events[0]" in field_names

    def test_independent_violations_across_all_fields(self) -> None:
        """Independent violations across every field are all observed (rule 23).

        ``state`` is wrong; each output collection is a well-typed tuple
        holding one bogus element, so each surfaces its own per-element
        violation.
        """
        result = ActionResult(
            state="not a state",  # type: ignore[arg-type]
            lifecycle_events=("nope",),  # type: ignore[arg-type]
            invoices=("nope",),  # type: ignore[arg-type]
            invoice_lines=("nope",),  # type: ignore[arg-type]
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        field_names = {f for f, _ in exc_info.value.violations}
        assert "state" in field_names
        assert "lifecycle_events[0]" in field_names
        assert "invoices[0]" in field_names
        assert "invoice_lines[0]" in field_names
