"""Tests for synthetic_billing.model.account_model."""

import pytest

from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.account_model import build_account


class TestBuildAccountHappyPath:
    """build_account derives a deterministic ID and returns a validated Account."""

    def test_returns_account(self) -> None:
        """The return type is Account."""
        acct = build_account(
            seed=42, account_ordinal=0, billing_cycle_day=15,
            region_code="US-WEST",
        )
        assert isinstance(acct, Account)

    def test_default_status_is_active(self) -> None:
        """Omitting account_status defaults to 'active'."""
        acct = build_account(
            seed=42, account_ordinal=0, billing_cycle_day=15,
            region_code="US-WEST",
        )
        assert acct.account_status == "active"

    def test_explicit_status(self) -> None:
        """An explicit account_status is stored unchanged."""
        acct = build_account(
            seed=42, account_ordinal=0, billing_cycle_day=15,
            region_code="US-WEST", account_status="suspended",
        )
        assert acct.account_status == "suspended"

    def test_ordinal_stored(self) -> None:
        """The account_ordinal is passed through to the Account."""
        acct = build_account(
            seed=42, account_ordinal=7, billing_cycle_day=1, region_code="EU",
        )
        assert acct.account_ordinal == 7


class TestBuildAccountIdDerivation:
    """build_account derives account_id via derive_id('account', seed, ordinal)."""

    def test_id_matches_derive_id(self) -> None:
        """The account_id matches a direct derive_id call."""
        acct = build_account(
            seed=42, account_ordinal=3, billing_cycle_day=15,
            region_code="US-WEST",
        )
        expected = derive_id("account", 42, 3)
        assert acct.account_id == expected

    def test_deterministic_across_calls(self) -> None:
        """Identical inputs produce the same account_id."""
        first = build_account(
            seed=1, account_ordinal=0, billing_cycle_day=10, region_code="AP",
        )
        second = build_account(
            seed=1, account_ordinal=0, billing_cycle_day=10, region_code="AP",
        )
        assert first.account_id == second.account_id

    def test_different_seeds_different_ids(self) -> None:
        """Different seeds produce different account IDs."""
        a = build_account(
            seed=1, account_ordinal=0, billing_cycle_day=10, region_code="AP",
        )
        b = build_account(
            seed=2, account_ordinal=0, billing_cycle_day=10, region_code="AP",
        )
        assert a.account_id != b.account_id

    def test_different_ordinals_different_ids(self) -> None:
        """Different ordinals produce different account IDs."""
        a = build_account(
            seed=42, account_ordinal=0, billing_cycle_day=10,
            region_code="AP",
        )
        b = build_account(
            seed=42, account_ordinal=1, billing_cycle_day=10,
            region_code="AP",
        )
        assert a.account_id != b.account_id


class TestBuildAccountValidation:
    """build_account propagates contract validation errors."""

    def test_rejects_invalid_billing_cycle_day(self) -> None:
        """Day 0 is rejected by the Account contract."""
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account(
                seed=42, account_ordinal=0, billing_cycle_day=0,
                region_code="US",
            )
        assert any(
            f == "billing_cycle_day" for f, _ in exc_info.value.violations
        )

    def test_rejects_invalid_status(self) -> None:
        """An unknown status is rejected by the Account contract."""
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account(
                seed=42, account_ordinal=0, billing_cycle_day=15,
                region_code="US", account_status="bogus",
            )
        assert any(
            f == "account_status" for f, _ in exc_info.value.violations
        )

    def test_rejects_blank_region(self) -> None:
        """A blank region_code is rejected by the Account contract."""
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account(
                seed=42, account_ordinal=0, billing_cycle_day=15,
                region_code="",
            )
        assert any(f == "region_code" for f, _ in exc_info.value.violations)
