"""Tests for synthetic_billing.contracts.event_contracts."""

import dataclasses

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.contracts.event_contracts import (
    LIFECYCLE_EVENT_TYPES,
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_event(**overrides) -> LifecycleEvent:
    """Build a valid LifecycleEvent via create_validated."""
    defaults = {
        "event_id": "evt-cancel-001",
        "simulation_month": 2,
        "event_type": SUBSCRIBER_CANCELLED_EVENT_TYPE,
        "account_id": "acct-001",
        "subscriber_id": "subscriber-001",
        "plan_code": "BASIC",
    }
    kw = {**defaults, **overrides}
    return LifecycleEvent.create_validated(
        kw["event_id"],
        kw["simulation_month"],
        kw["event_type"],
        kw["account_id"],
        kw["subscriber_id"],
        kw["plan_code"],
    )


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class TestLifecycleVocabulary:
    """Lifecycle event vocabulary is minimal and well-formed."""

    def test_subscriber_cancelled_event_type_value(self) -> None:
        """The cancellation event type is the literal `subscriber_cancelled`."""
        assert SUBSCRIBER_CANCELLED_EVENT_TYPE == "subscriber_cancelled"

    def test_lifecycle_event_types_contains_only_subscriber_cancelled(
        self,
    ) -> None:
        """LIFECYCLE_EVENT_TYPES contains exactly one entry in this slice."""
        assert LIFECYCLE_EVENT_TYPES == (SUBSCRIBER_CANCELLED_EVENT_TYPE,)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestLifecycleEventHappyPath:
    """Valid lifecycle events construct without errors."""

    def test_valid_event(self) -> None:
        """A valid subscriber_cancelled event constructs cleanly."""
        event = _valid_event()
        assert event.event_id == "evt-cancel-001"
        assert event.simulation_month == 2
        assert event.event_type == SUBSCRIBER_CANCELLED_EVENT_TYPE
        assert event.account_id == "acct-001"
        assert event.subscriber_id == "subscriber-001"
        assert event.plan_code == "BASIC"

    def test_month_two_is_accepted(self) -> None:
        """simulation_month = 2 is the earliest legal lifecycle month."""
        event = _valid_event(simulation_month=2)
        assert event.simulation_month == 2

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        event = _valid_event()
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.event_type = "upgrade"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _Validated protocol
# ---------------------------------------------------------------------------


class TestLifecycleEventValidatedProtocol:
    """LifecycleEvent exercises the _Validated mix-in correctly."""

    def test_is_validated_subclass(self) -> None:
        """LifecycleEvent inherits from _Validated."""
        assert issubclass(LifecycleEvent, _Validated)

    def test_validate_happy_path(self) -> None:
        """validate() on a valid instance returns None."""
        event = _valid_event()
        assert event.validate() is None

    def test_is_valid_true(self) -> None:
        """is_valid() returns True for a structurally valid instance."""
        event = _valid_event()
        assert event.is_valid() is True


# ---------------------------------------------------------------------------
# Type-check rejections (via create_validated)
# ---------------------------------------------------------------------------


class TestLifecycleEventTypeChecks:
    """create_validated rejects wrong constructor types via _type_check_specs."""

    def test_non_string_event_id(self) -> None:
        """An integer event_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(event_id=42)
        assert ("event_id", 42) in exc_info.value.violations

    def test_bool_simulation_month(self) -> None:
        """Bool simulation_month is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(simulation_month=True)
        assert ("simulation_month", True) in exc_info.value.violations

    def test_non_int_simulation_month(self) -> None:
        """A string simulation_month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(simulation_month="2")
        assert ("simulation_month", "2") in exc_info.value.violations

    def test_non_string_event_type(self) -> None:
        """An integer event_type is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(event_type=0)
        assert ("event_type", 0) in exc_info.value.violations

    def test_non_string_account_id(self) -> None:
        """A non-string account_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(account_id=42)
        assert ("account_id", 42) in exc_info.value.violations

    def test_non_string_subscriber_id(self) -> None:
        """A non-string subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(subscriber_id=42)
        assert ("subscriber_id", 42) in exc_info.value.violations

    def test_non_string_plan_code(self) -> None:
        """A non-string plan_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(plan_code=42)
        assert ("plan_code", 42) in exc_info.value.violations


# ---------------------------------------------------------------------------
# Structural-check rejections (via create_validated)
# ---------------------------------------------------------------------------


class TestLifecycleEventStructuralChecks:
    """Structural validation catches value-range and vocabulary errors."""

    def test_blank_event_id(self) -> None:
        """A whitespace-only event_id is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(event_id="   ")
        assert any(f == "event_id" for f, _ in exc_info.value.violations)

    def test_month_one_rejected(self) -> None:
        """simulation_month = 1 is the starter month and is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(simulation_month=1)
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_month_zero_rejected(self) -> None:
        """simulation_month = 0 is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(simulation_month=0)
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_negative_month_rejected(self) -> None:
        """A negative simulation_month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(simulation_month=-3)
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_unknown_event_type_rejected(self) -> None:
        """An event_type outside LIFECYCLE_EVENT_TYPES is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(event_type="plan_upgraded")
        assert any(f == "event_type" for f, _ in exc_info.value.violations)

    def test_blank_account_id(self) -> None:
        """An empty account_id is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(account_id="")
        assert any(f == "account_id" for f, _ in exc_info.value.violations)

    def test_blank_subscriber_id(self) -> None:
        """A whitespace-only subscriber_id is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(subscriber_id="   ")
        assert any(f == "subscriber_id" for f, _ in exc_info.value.violations)

    def test_blank_plan_code(self) -> None:
        """An empty plan_code is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(plan_code="")
        assert any(f == "plan_code" for f, _ in exc_info.value.violations)

    def test_multiple_violations_collected(self) -> None:
        """Multiple structural failures are collected into one error."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_event(
                event_id="",
                simulation_month=0,
                event_type="plan_upgraded",
                account_id="",
                subscriber_id="",
                plan_code="",
            )
        field_names = {f for f, _ in exc_info.value.violations}
        assert "event_id" in field_names
        assert "simulation_month" in field_names
        assert "event_type" in field_names
        assert "account_id" in field_names
        assert "subscriber_id" in field_names
        assert "plan_code" in field_names
