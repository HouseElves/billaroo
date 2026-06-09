"""Tests for synthetic_billing.contracts.subscriber_contracts."""

import dataclasses

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_FIELDS = {
    "subscriber_id": "sub001",
    "account_id": "acct001",
    "subscriber_ordinal": 0,
    "plan_code": "BASIC",
    "active": True,
}


def _make(**overrides) -> Subscriber:
    """Build a valid Subscriber via create_validated, applying *overrides*."""
    kw = {**_VALID_FIELDS, **overrides}
    return Subscriber.create_validated(
        kw["subscriber_id"],
        kw["account_id"],
        kw["subscriber_ordinal"],
        kw["plan_code"],
        kw["active"],
    )


# ---------------------------------------------------------------------------
# Happy path & _Validated protocol
# ---------------------------------------------------------------------------


class TestSubscriberHappyPath:
    """Subscriber stores validated fields in a frozen dataclass."""

    def test_is_validated_subclass(self) -> None:
        """Subscriber inherits from _Validated."""
        assert issubclass(Subscriber, _Validated)

    def test_constructs_with_defaults(self) -> None:
        """All fields are stored unchanged."""
        sub = _make()
        assert sub.subscriber_id == "sub001"
        assert sub.account_id == "acct001"
        assert sub.subscriber_ordinal == 0
        assert sub.plan_code == "BASIC"
        assert sub.active is True

    def test_inactive_subscriber(self) -> None:
        """An inactive subscriber is valid."""
        assert _make(active=False).active is False

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        sub = _make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sub.active = False  # type: ignore[misc]

    def test_validate_happy_path(self) -> None:
        """validate() on a valid subscriber returns None."""
        assert _make().validate() is None

    def test_is_valid_true(self) -> None:
        """is_valid() is True for a structurally valid subscriber."""
        assert _make().is_valid() is True

    def test_validity_check_true(self) -> None:
        """validity_check returns (True, name, instance) when valid."""
        sub = _make()
        passed, name, obj = sub.validity_check("sub")
        assert passed is True
        assert name == "sub"
        assert obj is sub


# ---------------------------------------------------------------------------
# Type-check rejections
# ---------------------------------------------------------------------------


class TestSubscriberTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_non_string_subscriber_id(self) -> None:
        """An integer subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(subscriber_id=42)
        assert ("subscriber_id", 42) in exc_info.value.violations

    def test_non_string_account_id(self) -> None:
        """An integer account_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_id=42)
        assert ("account_id", 42) in exc_info.value.violations

    def test_bool_ordinal(self) -> None:
        """Bool ordinal is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(subscriber_ordinal=True)
        assert ("subscriber_ordinal", True) in exc_info.value.violations

    def test_float_ordinal(self) -> None:
        """Float ordinal is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(subscriber_ordinal=1.0)
        assert ("subscriber_ordinal", 1.0) in exc_info.value.violations

    def test_non_string_plan_code(self) -> None:
        """An integer plan_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(plan_code=42)
        assert ("plan_code", 42) in exc_info.value.violations

    def test_int_active(self) -> None:
        """Integer 1 is rejected as not a bool."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(active=1)
        assert ("active", 1) in exc_info.value.violations

    def test_none_active(self) -> None:
        """None is rejected as not a bool."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(active=None)
        assert ("active", None) in exc_info.value.violations

    def test_string_active(self) -> None:
        """A string is rejected as not a bool."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(active="true")
        assert ("active", "true") in exc_info.value.violations


# ---------------------------------------------------------------------------
# Structural-check rejections
# ---------------------------------------------------------------------------


class TestSubscriberStructuralChecks:
    """Structural validation catches value and range errors."""

    def test_blank_subscriber_id(self) -> None:
        """An empty subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(subscriber_id="")
        assert any(
            f == "subscriber_id" for f, _ in exc_info.value.violations
        )

    def test_blank_account_id(self) -> None:
        """A whitespace-only account_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_id="   ")
        assert any(f == "account_id" for f, _ in exc_info.value.violations)

    def test_negative_ordinal(self) -> None:
        """A negative subscriber_ordinal is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(subscriber_ordinal=-1)
        assert any(
            f == "subscriber_ordinal" for f, _ in exc_info.value.violations
        )

    def test_blank_plan_code(self) -> None:
        """A blank plan_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(plan_code="")
        assert any(f == "plan_code" for f, _ in exc_info.value.violations)

    def test_multiple_violations_collected(self) -> None:
        """Multiple structural failures are collected into one error."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(
                subscriber_id="",
                account_id="",
                subscriber_ordinal=-1,
                plan_code="",
            )
        field_names = {f for f, _ in exc_info.value.violations}
        assert "subscriber_id" in field_names
        assert "account_id" in field_names
        assert "subscriber_ordinal" in field_names
        assert "plan_code" in field_names

    def test_is_valid_false(self) -> None:
        """Direct construction of an invalid subscriber yields is_valid()=False."""
        sub = Subscriber(
            subscriber_id="", account_id="acct", subscriber_ordinal=0,
            plan_code="BASIC", active=True,
        )
        assert sub.is_valid() is False
