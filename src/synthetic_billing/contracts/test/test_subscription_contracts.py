"""Tests for synthetic_billing.contracts.subscription_contracts."""

import dataclasses

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
    SUBSCRIPTION_ITEM_TYPES,
    SUBSCRIPTION_STATUSES,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _active_plan(**overrides) -> Subscription:
    """Build a valid active plan subscription via create_validated."""
    defaults = {
        "subscription_id": "sub-plan-001",
        "subscriber_id": "subscriber-001",
        "item_type": PLAN_ITEM_TYPE,
        "item_code": "BASIC",
        "start_month": 1,
        "end_month": None,
        "subscription_status": ACTIVE_SUBSCRIPTION_STATUS,
    }
    kw = {**defaults, **overrides}
    return Subscription.create_validated(
        kw["subscription_id"],
        kw["subscriber_id"],
        kw["item_type"],
        kw["item_code"],
        kw["start_month"],
        kw["end_month"],
        kw["subscription_status"],
    )


def _ended_plan(**overrides) -> Subscription:
    """Build a valid ended plan subscription via create_validated."""
    defaults = {
        "subscription_id": "sub-plan-002",
        "subscriber_id": "subscriber-001",
        "item_type": PLAN_ITEM_TYPE,
        "item_code": "BASIC",
        "start_month": 1,
        "end_month": 6,
        "subscription_status": ENDED_SUBSCRIPTION_STATUS,
    }
    kw = {**defaults, **overrides}
    return Subscription.create_validated(
        kw["subscription_id"],
        kw["subscriber_id"],
        kw["item_type"],
        kw["item_code"],
        kw["start_month"],
        kw["end_month"],
        kw["subscription_status"],
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Subscription vocabulary constants are well-formed."""

    def test_item_types_contains_plan_and_feature(self) -> None:
        """SUBSCRIPTION_ITEM_TYPES includes both plan and feature."""
        assert PLAN_ITEM_TYPE in SUBSCRIPTION_ITEM_TYPES
        assert FEATURE_ITEM_TYPE in SUBSCRIPTION_ITEM_TYPES

    def test_statuses_contains_active_and_ended(self) -> None:
        """SUBSCRIPTION_STATUSES includes both active and ended."""
        assert ACTIVE_SUBSCRIPTION_STATUS in SUBSCRIPTION_STATUSES
        assert ENDED_SUBSCRIPTION_STATUS in SUBSCRIPTION_STATUSES


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSubscriptionHappyPath:
    """Valid subscriptions construct without errors."""

    def test_active_plan_subscription(self) -> None:
        """An active plan subscription with no end_month is valid."""
        sub = _active_plan()
        assert sub.item_type == PLAN_ITEM_TYPE
        assert sub.subscription_status == ACTIVE_SUBSCRIPTION_STATUS
        assert sub.end_month is None

    def test_ended_plan_subscription(self) -> None:
        """An ended plan subscription with end_month >= start_month is valid."""
        sub = _ended_plan()
        assert sub.subscription_status == ENDED_SUBSCRIPTION_STATUS
        assert sub.end_month == 6

    def test_feature_subscription(self) -> None:
        """A feature subscription is structurally identical to a plan one."""
        sub = _active_plan(item_type=FEATURE_ITEM_TYPE, item_code="HD")
        assert sub.item_type == FEATURE_ITEM_TYPE
        assert sub.item_code == "HD"

    def test_end_month_equals_start_month(self) -> None:
        """A subscription that starts and ends in the same month is valid."""
        sub = _ended_plan(start_month=3, end_month=3)
        assert sub.start_month == 3
        assert sub.end_month == 3

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        sub = _active_plan()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sub.subscription_status = "ended"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _Validated protocol
# ---------------------------------------------------------------------------


class TestSubscriptionValidatedProtocol:
    """Subscription exercises the _Validated mix-in correctly."""

    def test_is_validated_subclass(self) -> None:
        """Subscription inherits from _Validated."""
        assert issubclass(Subscription, _Validated)

    def test_create_validated_happy_path(self) -> None:
        """create_validated returns a structurally valid Subscription."""
        sub = _active_plan()
        assert isinstance(sub, Subscription)

    def test_validate_happy_path(self) -> None:
        """validate() on a valid instance returns None."""
        sub = _active_plan()
        assert sub.validate() is None

    def test_is_valid_true(self) -> None:
        """is_valid() returns True for a structurally valid instance."""
        sub = _active_plan()
        assert sub.is_valid() is True

    def test_is_valid_false(self) -> None:
        """is_valid() returns False for a structurally invalid instance."""
        sub = Subscription(
            subscription_id="x", subscriber_id="y", item_type="bogus",
            item_code="z", start_month=1, end_month=None,
            subscription_status=ACTIVE_SUBSCRIPTION_STATUS,
        )
        assert sub.is_valid() is False

    def test_validity_check_true(self) -> None:
        """validity_check() returns (True, name, instance) when valid."""
        sub = _active_plan()
        passed, name, obj = sub.validity_check("sub")
        assert passed is True
        assert name == "sub"
        assert obj is sub

    def test_validity_check_false(self) -> None:
        """validity_check() returns (False, name, instance) when invalid."""
        sub = Subscription(
            subscription_id="x", subscriber_id="y", item_type="bogus",
            item_code="z", start_month=1, end_month=None,
            subscription_status=ACTIVE_SUBSCRIPTION_STATUS,
        )
        passed, name, obj = sub.validity_check("sub")
        assert passed is False
        assert name == "sub"
        assert obj is sub


# ---------------------------------------------------------------------------
# Type-check rejections (via create_validated)
# ---------------------------------------------------------------------------


class TestSubscriptionTypeChecks:
    """create_validated rejects wrong constructor types via _type_check_specs."""

    def test_non_string_subscription_id(self) -> None:
        """An integer subscription_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(subscription_id=42)
        assert ("subscription_id", 42) in exc_info.value.violations

    def test_non_string_subscriber_id(self) -> None:
        """An integer subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(subscriber_id=42)
        assert ("subscriber_id", 42) in exc_info.value.violations

    def test_bool_start_month(self) -> None:
        """Bool start_month is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(start_month=True)
        assert ("start_month", True) in exc_info.value.violations

    def test_non_int_start_month(self) -> None:
        """A string start_month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(start_month="1")
        assert ("start_month", "1") in exc_info.value.violations

    def test_bool_end_month(self) -> None:
        """Bool end_month is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _ended_plan(end_month=True)
        assert ("end_month", True) in exc_info.value.violations

    def test_non_int_end_month(self) -> None:
        """A string end_month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _ended_plan(end_month="6")
        assert ("end_month", "6") in exc_info.value.violations


# ---------------------------------------------------------------------------
# Structural-check rejections (via create_validated or validate)
# ---------------------------------------------------------------------------


class TestSubscriptionStructuralChecks:  # pylint: disable=too-many-public-methods
    """Structural validation catches value, range, and cross-field errors."""

    def test_blank_subscription_id(self) -> None:
        """A whitespace-only subscription_id is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(subscription_id="   ")
        assert any(f == "subscription_id" for f, _ in exc_info.value.violations)

    def test_blank_subscriber_id(self) -> None:
        """An empty subscriber_id is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(subscriber_id="")
        assert any(f == "subscriber_id" for f, _ in exc_info.value.violations)

    def test_invalid_item_type(self) -> None:
        """An item_type not in SUBSCRIPTION_ITEM_TYPES is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(item_type="bundle")
        assert any(f == "item_type" for f, _ in exc_info.value.violations)

    def test_blank_item_code(self) -> None:
        """A blank item_code is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(item_code="")
        assert any(f == "item_code" for f, _ in exc_info.value.violations)

    def test_start_month_below_one(self) -> None:
        """start_month must be >= 1."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(start_month=0)
        assert any(f == "start_month" for f, _ in exc_info.value.violations)

    def test_end_month_before_start_month(self) -> None:
        """end_month must be >= start_month when present."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _ended_plan(start_month=5, end_month=3)
        assert any(f == "end_month" for f, _ in exc_info.value.violations)

    def test_invalid_subscription_status(self) -> None:
        """A status not in SUBSCRIPTION_STATUSES is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(subscription_status="paused")
        assert any(f == "subscription_status" for f, _ in exc_info.value.violations)

    def test_active_with_end_month_rejected(self) -> None:
        """An active subscription must have end_month is None."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(end_month=6)
        assert any(f == "end_month" for f, _ in exc_info.value.violations)

    def test_ended_without_end_month_rejected(self) -> None:
        """An ended subscription must have a non-None end_month."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(
                subscription_status=ENDED_SUBSCRIPTION_STATUS,
                end_month=None,
            )
        assert any(f == "end_month" for f, _ in exc_info.value.violations)

    def test_multiple_violations_collected(self) -> None:
        """Multiple structural failures are collected into one error."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _active_plan(
                subscription_id="",
                item_type="bogus",
                item_code="",
                start_month=0,
            )
        field_names = {f for f, _ in exc_info.value.violations}
        assert "subscription_id" in field_names
        assert "item_type" in field_names
        assert "item_code" in field_names
        assert "start_month" in field_names
