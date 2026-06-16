"""Tests for synthetic_billing.simulate.simulation_result."""

import dataclasses
from decimal import Decimal

import pytest

from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.contracts.subscription_contracts import PLAN_ITEM_TYPE
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.billing_model import (
    build_invoice,
    build_invoice_line,
)
from synthetic_billing.simulate.simulation_result import SimulationResult
from synthetic_billing.simulate.simulation_state import SimulationState


def _empty_state() -> SimulationState:
    """Return a structurally valid empty simulation state."""
    return SimulationState.create_validated((), (), ())


_CANCEL_EVENT_FIXED_FIELDS: tuple[object, ...] = (
    2,  # simulation_month
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
    "acct-001",
)


def _cancel_event(label: str = "only") -> LifecycleEvent:
    """Build a labelled subscriber_cancelled lifecycle event."""
    args = (f"event-{label}",) + _CANCEL_EVENT_FIXED_FIELDS + (
        f"subscriber-{label}", "BASIC",
    )
    return LifecycleEvent.create_validated(*args)


def _invoice(label: str = "only") -> object:
    """Build a labelled invoice header for one account-month."""
    return build_invoice(f"acct-{label}", 1, 15, Decimal("29.99"))


def _invoice_line(invoice_id: str, label: str = "only") -> object:
    """Build a labelled invoice line for *invoice_id*."""
    return build_invoice_line(
        invoice_id, f"sub-{label}", f"pls-{label}",
        PLAN_ITEM_TYPE, "BASIC", Decimal("29.99"),
    )


class TestSimulationResultHappyPath:
    """Valid SimulationResult instances construct cleanly."""

    def test_empty_collections(self) -> None:
        """A result with no events or billing constructs cleanly."""
        state = _empty_state()
        result = SimulationResult.create_validated(state, (), (), ())
        assert result.state is state
        assert isinstance(result.lifecycle_events, tuple)
        assert not result.lifecycle_events
        assert not result.invoices
        assert not result.invoice_lines

    def test_with_events(self) -> None:
        """A result with one or more events preserves order."""
        state = _empty_state()
        events = (_cancel_event("a"), _cancel_event("b"))
        result = SimulationResult.create_validated(state, events, (), ())
        assert result.lifecycle_events == events

    def test_with_billing(self) -> None:
        """A result with invoices and lines preserves order."""
        state = _empty_state()
        invoice = _invoice("a")
        line = _invoice_line(invoice.invoice_id, "a")
        result = SimulationResult.create_validated(
            state, (), (invoice,), (line,),
        )
        assert result.invoices == (invoice,)
        assert result.invoice_lines == (line,)

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        state = _empty_state()
        result = SimulationResult.create_validated(state, (), (), ())
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.lifecycle_events = (_cancel_event(),)  # type: ignore[misc]


class TestSimulationResultTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_state_type_rejected(self) -> None:
        """A non-SimulationState state argument is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated("not a state", (), (), ())
        assert any(f == "state" for f, _ in exc_info.value.violations)

    def test_lifecycle_events_must_be_tuple(self) -> None:
        """A list passed as lifecycle_events is rejected."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(state, [], (), ())
        assert any(
            f == "lifecycle_events" for f, _ in exc_info.value.violations
        )

    def test_invoices_must_be_tuple(self) -> None:
        """A list passed as invoices is rejected."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(state, (), [], ())
        assert any(f == "invoices" for f, _ in exc_info.value.violations)

    def test_invoice_lines_must_be_tuple(self) -> None:
        """A list passed as invoice_lines is rejected."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(state, (), (), [])
        assert any(
            f == "invoice_lines" for f, _ in exc_info.value.violations
        )


# SimulationResult and ActionResult are deliberately distinct envelope
# types that share the same state-plus-billing-collections shape (D40),
# so their structural-validation tests exercise the same per-collection
# and direct-construction patterns.  The parallel test bodies are the
# expected mirror of two intentionally-separate types, not copy-paste to
# be collapsed; the duplicate-code report on them is suppressed at the
# test-class scope rather than by merging the two suites.
class TestSimulationResultStructuralChecks:  # pylint: disable=duplicate-code
    """Structural validation catches per-element and direct-construction errors."""

    def test_non_event_element_rejected(self) -> None:
        """A non-LifecycleEvent element is reported at its index."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(
                state, ("not an event",), (), (),
            )
        assert any(
            f == "lifecycle_events[0]"
            for f, _ in exc_info.value.violations
        )

    def test_non_invoice_element_rejected(self) -> None:
        """A non-Invoice element is reported at its index."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(
                state, (), ("not an invoice",), (),
            )
        assert any(
            f == "invoices[0]" for f, _ in exc_info.value.violations
        )

    def test_non_line_element_rejected(self) -> None:
        """A non-InvoiceLine element is reported at its index."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(
                state, (), (), ("not a line",),
            )
        assert any(
            f == "invoice_lines[0]" for f, _ in exc_info.value.violations
        )

    def test_direct_construction_non_tuple_invoices(self) -> None:
        """A non-tuple invoices surfaces only the tuple violation.

        Per rule 23, when one collection's top-level shape is wrong, its
        per-element checks are skipped while the other collections still
        report independently.
        """
        bad_payload: list = ["nope"]
        result = SimulationResult(
            state=_empty_state(),
            lifecycle_events=(),
            invoices=bad_payload,  # type: ignore[arg-type]
            invoice_lines=(),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        offending_fields = {field for field, _ in exc_info.value.violations}
        assert "invoices" in offending_fields
        assert "invoices[0]" not in offending_fields

    def test_direct_construction_independent_collections(self) -> None:
        """A bad invoice_lines top-level type does not mask a bad event element."""
        result = SimulationResult(
            state=_empty_state(),
            lifecycle_events=("not an event",),  # type: ignore[arg-type]
            invoices=(),
            invoice_lines="nope",  # type: ignore[arg-type]
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        offending_fields = {field for field, _ in exc_info.value.violations}
        # The well-typed-tuple lifecycle_events still surfaces its bad element.
        assert "lifecycle_events[0]" in offending_fields
        # The non-tuple invoice_lines surfaces only the top-level violation.
        assert "invoice_lines" in offending_fields
        assert "invoice_lines[0]" not in offending_fields

    def test_direct_construction_bad_state_surfaced(self) -> None:
        """Direct construction with a bogus state surfaces a state violation."""
        result = SimulationResult(
            state="not a state",  # type: ignore[arg-type]
            lifecycle_events=(),
            invoices=(),
            invoice_lines=(),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        assert any(f == "state" for f, _ in exc_info.value.violations)
