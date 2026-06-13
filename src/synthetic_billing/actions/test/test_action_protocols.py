"""Tests for synthetic_billing.actions.action_protocols."""

import dataclasses

import pytest

from synthetic_billing.actions.action_protocols import ActionResult
from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.exceptions import InvalidRequestError
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


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestActionResultHappyPath:
    """Valid ActionResult instances construct without errors."""

    def test_empty_events(self) -> None:
        """An ActionResult with no lifecycle events constructs cleanly."""
        state = _empty_state()
        result = ActionResult.create_validated(state, ())
        assert result.state is state
        assert isinstance(result.lifecycle_events, tuple)
        assert not result.lifecycle_events

    def test_single_event(self) -> None:
        """An ActionResult with one valid lifecycle event constructs."""
        state = _empty_state()
        event = _cancel_event()
        result = ActionResult.create_validated(state, (event,))
        assert result.lifecycle_events == (event,)

    def test_multiple_events(self) -> None:
        """An ActionResult with multiple valid lifecycle events constructs."""
        state = _empty_state()
        events = (_cancel_event("evt-1"), _cancel_event("evt-2"))
        result = ActionResult.create_validated(state, events)
        assert result.lifecycle_events == events

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        state = _empty_state()
        result = ActionResult.create_validated(state, ())
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.lifecycle_events = (_cancel_event(),)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Type-check rejections (via create_validated)
# ---------------------------------------------------------------------------


class TestActionResultTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_state_type_rejected(self) -> None:
        """A non-SimulationState state argument is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated("not a state", ())
        assert any(f == "state" for f, _ in exc_info.value.violations)

    def test_lifecycle_events_must_be_tuple(self) -> None:
        """A list passed as lifecycle_events is rejected by the type spec."""
        state = _empty_state()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, [])
        assert any(
            f == "lifecycle_events" for f, _ in exc_info.value.violations
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
            ActionResult.create_validated(state, ("not an event",))
        assert any(
            f == "lifecycle_events[0]"
            for f, _ in exc_info.value.violations
        )

    def test_mixed_valid_and_invalid_elements(self) -> None:
        """Per-element checks report only the bogus elements (rule 23)."""
        state = _empty_state()
        good = _cancel_event()
        with pytest.raises(InvalidRequestError) as exc_info:
            ActionResult.create_validated(state, (good, "nope"))
        field_names = {f for f, _ in exc_info.value.violations}
        assert "lifecycle_events[0]" not in field_names
        assert "lifecycle_events[1]" in field_names

    def test_direct_construction_state_surfaced(self) -> None:
        """Direct construction with a bogus state surfaces a state violation.

        Direct construction bypasses create_validated and its constructor
        type checks; the structural re-check ensures the violation is
        still observable (rule 23).
        """
        result = ActionResult(state="not a state", lifecycle_events=())  # type: ignore[arg-type]
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        assert any(f == "state" for f, _ in exc_info.value.violations)

    def test_direct_construction_non_tuple_lifecycle_events_surfaced(
        self,
    ) -> None:
        """A non-tuple lifecycle_events surfaces the tuple violation only.

        Per-element checks are skipped because iterating a non-tuple is
        not a safely observable check in this contract (rule 23).
        """
        state = _empty_state()
        result = ActionResult(
            state=state,
            lifecycle_events=["nope"],  # type: ignore[arg-type]
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        field_names = {f for f, _ in exc_info.value.violations}
        assert "lifecycle_events" in field_names
        assert "lifecycle_events[0]" not in field_names

    def test_multiple_violations_collected_over_typed_subsets(self) -> None:
        """Bad state plus a bogus element produce two violations (rule 23).

        With ``state`` wrong and ``lifecycle_events`` correctly a tuple
        containing one bogus element, both violations are observed.
        """
        result = ActionResult(
            state="not a state",  # type: ignore[arg-type]
            lifecycle_events=("nope",),  # type: ignore[arg-type]
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            result.validate()
        field_names = {f for f, _ in exc_info.value.violations}
        assert "state" in field_names
        assert "lifecycle_events[0]" in field_names
