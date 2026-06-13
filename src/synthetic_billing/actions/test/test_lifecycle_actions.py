"""Tests for synthetic_billing.actions.lifecycle_actions."""

import dataclasses

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.actions.lifecycle_actions import (
    CancelSubscriberIntent,
    build_cancel_subscriber_action_chain,
)
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_intent(**overrides) -> CancelSubscriberIntent:
    """Build a valid CancelSubscriberIntent via create_validated."""
    defaults = {
        "simulation_month": 2,
        "subscriber_id": "subscriber-001",
    }
    kw = {**defaults, **overrides}
    return CancelSubscriberIntent.create_validated(
        kw["simulation_month"],
        kw["subscriber_id"],
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestCancelSubscriberIntentHappyPath:
    """Valid cancellation intents construct without errors."""

    def test_valid_intent(self) -> None:
        """A valid intent for month 2 constructs cleanly."""
        intent = _valid_intent()
        assert intent.simulation_month == 2
        assert intent.subscriber_id == "subscriber-001"

    def test_month_two_is_accepted(self) -> None:
        """simulation_month = 2 is the earliest legal cancellation month."""
        intent = _valid_intent(simulation_month=2)
        assert intent.simulation_month == 2

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        intent = _valid_intent()
        with pytest.raises(dataclasses.FrozenInstanceError):
            intent.simulation_month = 3  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _Validated protocol
# ---------------------------------------------------------------------------


class TestCancelSubscriberIntentValidatedProtocol:
    """CancelSubscriberIntent exercises the _Validated mix-in correctly."""

    def test_is_validated_subclass(self) -> None:
        """CancelSubscriberIntent inherits from _Validated."""
        assert issubclass(CancelSubscriberIntent, _Validated)

    def test_validate_happy_path(self) -> None:
        """validate() on a valid instance returns None."""
        intent = _valid_intent()
        assert intent.validate() is None

    def test_is_valid_true(self) -> None:
        """is_valid() returns True for a structurally valid instance."""
        intent = _valid_intent()
        assert intent.is_valid() is True


# ---------------------------------------------------------------------------
# Type-check rejections (via create_validated)
# ---------------------------------------------------------------------------


class TestCancelSubscriberIntentTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_bool_simulation_month(self) -> None:
        """Bool simulation_month is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_intent(simulation_month=True)
        assert ("simulation_month", True) in exc_info.value.violations

    def test_non_int_simulation_month(self) -> None:
        """A string simulation_month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_intent(simulation_month="2")
        assert ("simulation_month", "2") in exc_info.value.violations

    def test_non_string_subscriber_id(self) -> None:
        """A non-string subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_intent(subscriber_id=42)
        assert ("subscriber_id", 42) in exc_info.value.violations


# ---------------------------------------------------------------------------
# Structural-check rejections (via create_validated)
# ---------------------------------------------------------------------------


class TestCancelSubscriberIntentStructuralChecks:
    """Structural validation catches value-range and shape errors."""

    def test_month_one_rejected(self) -> None:
        """simulation_month = 1 is the starter month and is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_intent(simulation_month=1)
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_blank_subscriber_id(self) -> None:
        """A whitespace-only subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _valid_intent(subscriber_id="   ")
        assert any(f == "subscriber_id" for f, _ in exc_info.value.violations)


# ---------------------------------------------------------------------------
# Stub: build_cancel_subscriber_action_chain
# ---------------------------------------------------------------------------


class TestBuildCancelSubscriberActionChainStub:
    """The chain-builder entry point is intentionally unimplemented (D38)."""

    def test_raises_not_implemented(self) -> None:
        """The function raises NotImplementedError immediately."""
        intent = _valid_intent()
        with pytest.raises(NotImplementedError):
            build_cancel_subscriber_action_chain(intent)

    def test_message_names_the_function(self) -> None:
        """The exception message names the function and its status."""
        intent = _valid_intent()
        with pytest.raises(NotImplementedError) as exc_info:
            build_cancel_subscriber_action_chain(intent)
        message = str(exc_info.value)
        assert "build_cancel_subscriber_action_chain" in message
        assert "not implemented" in message
