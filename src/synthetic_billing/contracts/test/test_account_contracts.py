"""Tests for synthetic_billing.contracts.account_contracts."""

import dataclasses

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.contracts.account_contracts import (
    ACCOUNT_STATUSES,
    Account,
)
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_FIELDS = {
    "account_id": "abc123",
    "account_ordinal": 0,
    "billing_cycle_day": 15,
    "region_code": "US-WEST",
    "account_status": "active",
}


def _make(**overrides) -> Account:
    """Build a valid Account via create_validated, applying *overrides*."""
    kw = {**_VALID_FIELDS, **overrides}
    return Account.create_validated(
        kw["account_id"],
        kw["account_ordinal"],
        kw["billing_cycle_day"],
        kw["region_code"],
        kw["account_status"],
    )


# ---------------------------------------------------------------------------
# Happy path & _Validated protocol
# ---------------------------------------------------------------------------


class TestAccountHappyPath:
    """Account stores validated fields in a frozen dataclass."""

    def test_is_validated_subclass(self) -> None:
        """Account inherits from _Validated."""
        assert issubclass(Account, _Validated)

    def test_constructs_with_defaults(self) -> None:
        """All fields are stored unchanged."""
        acct = _make()
        assert acct.account_id == "abc123"
        assert acct.account_ordinal == 0
        assert acct.billing_cycle_day == 15
        assert acct.region_code == "US-WEST"
        assert acct.account_status == "active"

    def test_all_statuses_accepted(self) -> None:
        """Every status in ACCOUNT_STATUSES is valid."""
        for status in ACCOUNT_STATUSES:
            assert _make(account_status=status).account_status == status

    def test_billing_cycle_day_lower_bound(self) -> None:
        """Day 1 is the minimum valid billing cycle day."""
        assert _make(billing_cycle_day=1).billing_cycle_day == 1

    def test_billing_cycle_day_upper_bound(self) -> None:
        """Day 28 is the maximum valid billing cycle day."""
        assert _make(billing_cycle_day=28).billing_cycle_day == 28

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        acct = _make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            acct.account_status = "closed"  # type: ignore[misc]

    def test_validate_happy_path(self) -> None:
        """validate() on a valid account returns None."""
        assert _make().validate() is None

    def test_is_valid_true(self) -> None:
        """is_valid() is True for a structurally valid account."""
        assert _make().is_valid() is True

    def test_validity_check_true(self) -> None:
        """validity_check returns (True, name, instance) when valid."""
        acct = _make()
        passed, name, obj = acct.validity_check("acct")
        assert passed is True
        assert name == "acct"
        assert obj is acct


# ---------------------------------------------------------------------------
# Type-check rejections
# ---------------------------------------------------------------------------


class TestAccountTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_non_string_account_id(self) -> None:
        """An integer account_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_id=42)
        assert ("account_id", 42) in exc_info.value.violations

    def test_bool_ordinal(self) -> None:
        """Bool ordinal is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_ordinal=True)
        assert ("account_ordinal", True) in exc_info.value.violations

    def test_float_ordinal(self) -> None:
        """Float ordinal is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_ordinal=1.0)
        assert ("account_ordinal", 1.0) in exc_info.value.violations

    def test_bool_billing_cycle_day(self) -> None:
        """Bool billing_cycle_day is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(billing_cycle_day=True)
        assert ("billing_cycle_day", True) in exc_info.value.violations

    def test_float_billing_cycle_day(self) -> None:
        """Float billing_cycle_day is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(billing_cycle_day=15.0)
        assert ("billing_cycle_day", 15.0) in exc_info.value.violations

    def test_non_string_region_code(self) -> None:
        """An integer region_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(region_code=42)
        assert ("region_code", 42) in exc_info.value.violations

    def test_non_string_status(self) -> None:
        """An integer account_status is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_status=42)
        assert ("account_status", 42) in exc_info.value.violations


# ---------------------------------------------------------------------------
# Structural-check rejections
# ---------------------------------------------------------------------------


class TestAccountStructuralChecks:
    """Structural validation catches value, range, and vocabulary errors."""

    def test_blank_account_id(self) -> None:
        """A whitespace-only account_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_id="   ")
        assert any(f == "account_id" for f, _ in exc_info.value.violations)

    def test_negative_ordinal(self) -> None:
        """A negative account_ordinal is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_ordinal=-1)
        assert any(
            f == "account_ordinal" for f, _ in exc_info.value.violations
        )

    def test_billing_cycle_day_zero(self) -> None:
        """Day 0 is below the valid range."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(billing_cycle_day=0)
        assert any(
            f == "billing_cycle_day" for f, _ in exc_info.value.violations
        )

    def test_billing_cycle_day_29(self) -> None:
        """Day 29 is above the valid range."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(billing_cycle_day=29)
        assert any(
            f == "billing_cycle_day" for f, _ in exc_info.value.violations
        )

    def test_blank_region_code(self) -> None:
        """An empty region_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(region_code="")
        assert any(f == "region_code" for f, _ in exc_info.value.violations)

    def test_unknown_status(self) -> None:
        """A string not in ACCOUNT_STATUSES is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(account_status="unknown")
        assert any(
            f == "account_status" for f, _ in exc_info.value.violations
        )

    def test_multiple_violations_collected(self) -> None:
        """Multiple structural failures are collected into one error."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make(
                account_id="",
                account_ordinal=-1,
                billing_cycle_day=0,
                region_code="",
                account_status="unknown",
            )
        field_names = {f for f, _ in exc_info.value.violations}
        assert "account_id" in field_names
        assert "account_ordinal" in field_names
        assert "billing_cycle_day" in field_names
        assert "region_code" in field_names
        assert "account_status" in field_names

    def test_is_valid_false(self) -> None:
        """Direct construction of an invalid account yields is_valid()=False."""
        acct = Account(
            account_id="x", account_ordinal=0, billing_cycle_day=15,
            region_code="US", account_status="unknown",
        )
        assert acct.is_valid() is False


class TestAccountStatusesConstant:
    """ACCOUNT_STATUSES is a non-empty tuple of strings."""

    def test_is_tuple(self) -> None:
        """ACCOUNT_STATUSES is a tuple."""
        assert isinstance(ACCOUNT_STATUSES, tuple)

    def test_non_empty(self) -> None:
        """ACCOUNT_STATUSES contains at least one entry."""
        assert len(ACCOUNT_STATUSES) >= 1
