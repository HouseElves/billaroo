"""Tests for synthetic_billing.simulate.simulation_result."""

import dataclasses

import pytest

from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.exceptions import InvalidRequestError
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


class TestSimulationResultHappyPath:
    """Valid SimulationResult instances construct cleanly."""

    def test_empty_events(self) -> None:
        """A result with no lifecycle events constructs cleanly."""
        state = _empty_state()
        result = SimulationResult.create_validated(state, ())
        assert result.state is state
        assert isinstance(result.lifecycle_events, tuple)
        assert not result.lifecycle_events

    def test_with_events(self) -> None:
        """A result with one or more events preserves order."""
        state = _empty_state()
        events = (_cancel_event("a"), _cancel_event("b"))
        result = SimulationResult.create_validated(state, events)
        assert result.lifecycle_events == events

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        state = _empty_state()
        result = SimulationResult.create_validated(state, ())
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.lifecycle_events = (_cancel_event(),)  # type: ignore[misc]


class TestSimulationResultTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_state_type_rejected(self) -> None:
        """A non-SimulationState state argument is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated("not a state", ())
        assert any(f == "state" for f, _ in exc_info.value.violations)

    def test_lifecycle_events_must_be_tuple(self) -> None:
        """A list passed as lifecycle_events is rejected."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(state, [])
        assert any(
            f == "lifecycle_events" for f, _ in exc_info.value.violations
        )


class TestSimulationResultStructuralChecks:
    """Structural validation catches per-element and direct-construction errors."""

    def test_non_event_element_rejected(self) -> None:
        """A non-LifecycleEvent element is reported at its index."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationResult.create_validated(state, ("not an event",))
        assert any(
            f == "lifecycle_events[0]"
            for f, _ in exc_info.value.violations
        )

    def test_direct_construction_non_tuple_lifecycle_events(self) -> None:
        """A non-tuple lifecycle_events surfaces only the tuple violation."""
        bad_payload: list = ["nope"]
        result = SimulationResult(
            state=_empty_state(),
            lifecycle_events=bad_payload,  # type: ignore[arg-type]
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        offending_fields = {field for field, _ in exc_info.value.violations}
        assert "lifecycle_events" in offending_fields
        # Per-element checks are skipped when the top-level shape is wrong,
        # so no indexed lifecycle_events[N] violation appears.
        assert "lifecycle_events[0]" not in offending_fields

    def test_direct_construction_bad_state_surfaced(self) -> None:
        """Direct construction with a bogus state surfaces a state violation."""
        result = SimulationResult(
            state="not a state",  # type: ignore[arg-type]
            lifecycle_events=(),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        assert any(f == "state" for f, _ in exc_info.value.violations)
