"""Tests for synthetic_billing.contracts.account_contracts."""

import dataclasses

import pytest

from synthetic_billing.contracts.account_contracts import (
    ACCOUNT_STATUSES,
    Account,
)


def _account(**overrides) -> Account:
    """Build a valid Account with defaults, applying *overrides*."""
    defaults = {
        "account_id": "abc123",
        "account_ordinal": 0,
        "billing_cycle_day": 15,
        "region_code": "US-WEST",
        "account_status": "active",
    }
    return Account(**{**defaults, **overrides})


class TestAccountHappyPath:
    """Account stores validated fields in a frozen dataclass."""

    def test_constructs_with_defaults(self) -> None:
        """All fields are stored unchanged."""
        acct = _account()
        assert acct.account_id == "abc123"
        assert acct.account_ordinal == 0
        assert acct.billing_cycle_day == 15
        assert acct.region_code == "US-WEST"
        assert acct.account_status == "active"

    def test_all_statuses_accepted(self) -> None:
        """Every status in ACCOUNT_STATUSES is valid."""
        for status in ACCOUNT_STATUSES:
            acct = _account(account_status=status)
            assert acct.account_status == status

    def test_billing_cycle_day_lower_bound(self) -> None:
        """Day 1 is the minimum valid billing cycle day."""
        acct = _account(billing_cycle_day=1)
        assert acct.billing_cycle_day == 1

    def test_billing_cycle_day_upper_bound(self) -> None:
        """Day 28 is the maximum valid billing cycle day."""
        acct = _account(billing_cycle_day=28)
        assert acct.billing_cycle_day == 28

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        acct = _account()
        with pytest.raises(dataclasses.FrozenInstanceError):
            acct.account_status = "closed"  # type: ignore[misc]


class TestAccountIdValidation:
    """Account rejects invalid account_id values."""

    def test_rejects_non_string_id(self) -> None:
        """An integer account_id is not a string."""
        with pytest.raises(TypeError, match="account_id"):
            _account(account_id=42)

    def test_rejects_blank_id(self) -> None:
        """A whitespace-only account_id is blank."""
        with pytest.raises(ValueError, match="account_id"):
            _account(account_id="   ")

    def test_rejects_empty_id(self) -> None:
        """An empty account_id is blank."""
        with pytest.raises(ValueError, match="account_id"):
            _account(account_id="")


class TestAccountOrdinalValidation:
    """Account rejects invalid account_ordinal values."""

    def test_rejects_bool_ordinal(self) -> None:
        """Bool is rejected despite being an int subclass."""
        with pytest.raises(TypeError, match="account_ordinal"):
            _account(account_ordinal=True)

    def test_rejects_float_ordinal(self) -> None:
        """Float is not a valid ordinal."""
        with pytest.raises(TypeError, match="account_ordinal"):
            _account(account_ordinal=1.0)

    def test_rejects_negative_ordinal(self) -> None:
        """Negative ordinals are invalid."""
        with pytest.raises(ValueError, match="account_ordinal"):
            _account(account_ordinal=-1)


class TestBillingCycleDayValidation:
    """Account rejects invalid billing_cycle_day values."""

    def test_rejects_bool(self) -> None:
        """Bool is rejected despite being an int subclass."""
        with pytest.raises(TypeError, match="billing_cycle_day"):
            _account(billing_cycle_day=True)

    def test_rejects_float(self) -> None:
        """Float is not a valid billing cycle day."""
        with pytest.raises(TypeError, match="billing_cycle_day"):
            _account(billing_cycle_day=15.0)

    def test_rejects_zero(self) -> None:
        """Day 0 is below the valid range."""
        with pytest.raises(ValueError, match="billing_cycle_day"):
            _account(billing_cycle_day=0)

    def test_rejects_29(self) -> None:
        """Day 29 is above the valid range."""
        with pytest.raises(ValueError, match="billing_cycle_day"):
            _account(billing_cycle_day=29)

    def test_rejects_negative(self) -> None:
        """Negative days are invalid."""
        with pytest.raises(ValueError, match="billing_cycle_day"):
            _account(billing_cycle_day=-1)


class TestRegionCodeValidation:
    """Account rejects invalid region_code values."""

    def test_rejects_non_string(self) -> None:
        """An integer region_code is not a string."""
        with pytest.raises(TypeError, match="region_code"):
            _account(region_code=42)

    def test_rejects_blank(self) -> None:
        """An empty region_code is blank."""
        with pytest.raises(ValueError, match="region_code"):
            _account(region_code="")


class TestAccountStatusValidation:
    """Account rejects invalid account_status values."""

    def test_rejects_non_string(self) -> None:
        """An integer account_status is not a string."""
        with pytest.raises(TypeError, match="account_status"):
            _account(account_status=42)

    def test_rejects_unknown_status(self) -> None:
        """A string not in ACCOUNT_STATUSES is rejected."""
        with pytest.raises(ValueError, match="account_status"):
            _account(account_status="unknown")

    def test_statuses_constant_is_tuple(self) -> None:
        """ACCOUNT_STATUSES is a tuple of at least one entry."""
        assert isinstance(ACCOUNT_STATUSES, tuple)
        assert len(ACCOUNT_STATUSES) >= 1
