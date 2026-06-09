"""Tests for simulation_state.py.

Validates that SimulationState enforces element types, ID uniqueness,
and cross-referential integrity via the _Validated vocabulary (D30).
"""

from __future__ import annotations

import pytest

from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.contracts.subscription_contracts import Subscription
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.account_model import build_account
from synthetic_billing.model.catalog_model import build_default_catalog
from synthetic_billing.model.subscriber_model import build_subscriber
from synthetic_billing.model.subscription_model import build_plan_subscription
from synthetic_billing.simulate.simulation_state import SimulationState


# ---- test helpers ----

def _make_catalog() -> Catalog:
    """Build a minimal catalog for tests."""
    return build_default_catalog()


def _make_account(seed: int = 42, ordinal: int = 0) -> Account:
    """Build a test account."""
    return build_account(
        seed=seed, account_ordinal=ordinal,
        billing_cycle_day=15, region_code="US-WEST",
    )


def _make_subscriber(
    account_id: str, plan_code: str = "BASIC",
    catalog: Catalog | None = None,
) -> Subscriber:
    """Build a test subscriber."""
    cat = catalog or _make_catalog()
    return build_subscriber(
        account_id=account_id,
        subscriber_ordinal=0,
        plan_code=plan_code,
        catalog=cat,
    )


def _make_plan_sub(
    subscriber_id: str, plan_code: str = "BASIC",
    catalog: Catalog | None = None,
) -> Subscription:
    """Build a test plan subscription."""
    cat = catalog or _make_catalog()
    return build_plan_subscription(
        subscriber_id=subscriber_id,
        plan_code=plan_code,
        start_month=1,
        catalog=cat,
    )


def _make_simple_state() -> SimulationState:
    """Build a minimal valid state with one account/subscriber/subscription."""
    cat = _make_catalog()
    acct = _make_account()
    sub = _make_subscriber(acct.account_id, catalog=cat)
    plan_sub = _make_plan_sub(sub.subscriber_id, sub.plan_code, catalog=cat)
    return SimulationState.create_validated(
        (acct,), (sub,), (plan_sub,),
    )


# ---- happy-path tests ----

class TestSimulationStateConstruction:
    """SimulationState construction via create_validated."""

    def test_minimal_valid_state(self) -> None:
        """A single account/subscriber/subscription forms a valid state."""
        state = _make_simple_state()
        assert len(state.accounts) == 1
        assert len(state.subscribers) == 1
        assert len(state.subscriptions) == 1

    def test_empty_tuples_valid(self) -> None:
        """An empty state (no accounts, subscribers, subscriptions) is valid."""
        state = SimulationState.create_validated((), (), ())
        assert not state.accounts
        assert not state.subscribers
        assert not state.subscriptions

    def test_multiple_accounts(self) -> None:
        """Multiple accounts with their subscribers and subscriptions."""
        cat = _make_catalog()
        accts = [_make_account(ordinal=i) for i in range(3)]
        subs = [
            _make_subscriber(a.account_id, catalog=cat) for a in accts
        ]
        plan_subs = [
            _make_plan_sub(s.subscriber_id, s.plan_code, catalog=cat)
            for s in subs
        ]
        state = SimulationState.create_validated(
            tuple(accts), tuple(subs), tuple(plan_subs),
        )
        assert len(state.accounts) == 3
        assert len(state.subscribers) == 3
        assert len(state.subscriptions) == 3

    def test_frozen(self) -> None:
        """SimulationState is immutable."""
        state = _make_simple_state()
        with pytest.raises(AttributeError):
            state.accounts = ()  # type: ignore[misc]

    def test_is_valid_true(self) -> None:
        """is_valid() returns True for a well-formed state."""
        state = _make_simple_state()
        assert state.is_valid()

    def test_validity_check_tuple(self) -> None:
        """validity_check returns a passing check tuple."""
        state = _make_simple_state()
        passed, field, value = state.validity_check("state")
        assert passed is True
        assert field == "state"
        assert value is state


# ---- type-check failures ----

class TestSimulationStateTypeChecks:
    """Constructor type checks via create_validated."""

    def test_accounts_not_tuple(self) -> None:
        """Passing a list for accounts raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated([], (), ())
        assert any(
            f == "accounts" for f, _ in exc_info.value.violations
        )

    def test_subscribers_not_tuple(self) -> None:
        """Passing a list for subscribers raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated((), [], ())
        assert any(
            f == "subscribers" for f, _ in exc_info.value.violations
        )

    def test_subscriptions_not_tuple(self) -> None:
        """Passing a list for subscriptions raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated((), (), [])
        assert any(
            f == "subscriptions" for f, _ in exc_info.value.violations
        )

    def test_all_three_wrong_type(self) -> None:
        """All three wrong types collected in one error."""
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated([], [], [])
        assert len(exc_info.value.violations) == 3

    def test_wrong_argument_count(self) -> None:
        """Too few arguments raises TypeError."""
        with pytest.raises(TypeError, match="expected 3"):
            SimulationState.create_validated((), ())

    def test_validate_safe_when_top_level_not_tuple(self) -> None:
        """Direct-construction with non-tuple top-level fields is invalid.

        Tuple-ness is checked at both the constructor-validation layer
        (``_type_check_specs``) and the structural-checks layer so that
        direct-construction callers who bypass ``create_validated`` are
        still reported as invalid rather than silently passing
        (constitution rule 23).
        """
        # Direct construction bypasses create_validated.
        state = SimulationState(
            accounts=42,           # type: ignore[arg-type]
            subscribers="not-tuple",  # type: ignore[arg-type]
            subscriptions=None,    # type: ignore[arg-type]
        )
        assert state.is_valid() is False
        with pytest.raises(InvalidRequestError) as exc_info:
            state.validate()
        fields = [f for f, _ in exc_info.value.violations]
        assert "accounts" in fields
        assert "subscribers" in fields
        assert "subscriptions" in fields

    def test_structural_checks_safe_when_one_field_not_tuple(self) -> None:
        """Mixed valid and non-tuple fields surface independent violations.

        ``accounts`` is a tuple with duplicate IDs (the duplicate-account
        check must fire); ``subscribers`` is a non-tuple (the top-level
        type check must fire); both violations are collected in the same
        ``InvalidRequestError``.
        """
        acct = _make_account()
        state = SimulationState(
            accounts=(acct, acct),  # duplicate account IDs
            subscribers=42,         # type: ignore[arg-type]
            subscriptions=(),
        )
        assert state.is_valid() is False
        with pytest.raises(InvalidRequestError) as exc_info:
            state.validate()
        violations = exc_info.value.violations
        # Duplicate account IDs surface as an "accounts" violation
        # whose observed value is the duplicate-bearing ID list.
        assert any(
            field == "accounts" and isinstance(value, list)
            for field, value in violations
        )
        # Non-tuple subscribers surface as a "subscribers" violation
        # whose observed value is the offending non-tuple itself.
        assert any(
            field == "subscribers" and value == 42
            for field, value in violations
        )


# ---- element type failures ----

class TestSimulationStateElementTypes:
    """Element-type checks within tuples."""

    def test_bad_account_element(self) -> None:
        """Non-Account in accounts tuple raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(("not-an-account",), (), ())
        fields = [f for f, _ in exc_info.value.violations]
        assert "accounts[0]" in fields

    def test_bad_subscriber_element(self) -> None:
        """Non-Subscriber in subscribers tuple raises InvalidRequestError."""
        acct = _make_account()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated((acct,), ("bad",), ())
        fields = [f for f, _ in exc_info.value.violations]
        assert "subscribers[0]" in fields

    def test_bad_subscription_element(self) -> None:
        """Non-Subscription in subscriptions tuple raises InvalidRequestError."""
        cat = _make_catalog()
        acct = _make_account()
        sub = _make_subscriber(acct.account_id, catalog=cat)
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(
                (acct,), (sub,), (42,),
            )
        fields = [f for f, _ in exc_info.value.violations]
        assert "subscriptions[0]" in fields


# ---- ID uniqueness failures ----

class TestSimulationStateIdUniqueness:
    """ID uniqueness checks."""

    def test_duplicate_account_ids(self) -> None:
        """Duplicate account IDs are detected."""
        acct = _make_account()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(
                (acct, acct), (), (),
            )
        fields = [f for f, _ in exc_info.value.violations]
        assert "accounts" in fields

    def test_duplicate_subscriber_ids(self) -> None:
        """Duplicate subscriber IDs are detected."""
        cat = _make_catalog()
        acct = _make_account()
        sub = _make_subscriber(acct.account_id, catalog=cat)
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(
                (acct,), (sub, sub), (),
            )
        fields = [f for f, _ in exc_info.value.violations]
        assert "subscribers" in fields

    def test_duplicate_subscription_ids(self) -> None:
        """Duplicate subscription IDs are detected."""
        cat = _make_catalog()
        acct = _make_account()
        sub = _make_subscriber(acct.account_id, catalog=cat)
        plan_sub = _make_plan_sub(
            sub.subscriber_id, sub.plan_code, catalog=cat,
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(
                (acct,), (sub,), (plan_sub, plan_sub),
            )
        fields = [f for f, _ in exc_info.value.violations]
        assert "subscriptions" in fields


# ---- cross-reference failures ----

class TestSimulationStateCrossReferences:
    """Cross-referential integrity checks."""

    def test_subscriber_dangling_account_id(self) -> None:
        """Subscriber with no matching account raises InvalidRequestError."""
        cat = _make_catalog()
        acct = _make_account(ordinal=0)
        # Build subscriber against a *different* account so its
        # account_id doesn't match what's in the state.
        other_acct = _make_account(ordinal=99)
        sub = _make_subscriber(other_acct.account_id, catalog=cat)
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(
                (acct,), (sub,), (),
            )
        fields = [f for f, _ in exc_info.value.violations]
        assert any("account_id" in f for f in fields)

    def test_subscription_dangling_subscriber_id(self) -> None:
        """Subscription with no matching subscriber raises InvalidRequestError."""
        cat = _make_catalog()
        acct = _make_account()
        sub = _make_subscriber(acct.account_id, catalog=cat)
        # Build subscription against a different subscriber.
        other_acct = _make_account(ordinal=99)
        other_sub = _make_subscriber(other_acct.account_id, catalog=cat)
        plan_sub = _make_plan_sub(
            other_sub.subscriber_id, other_sub.plan_code, catalog=cat,
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(
                (acct,), (sub,), (plan_sub,),
            )
        fields = [f for f, _ in exc_info.value.violations]
        assert any("subscriber_id" in f for f in fields)


# ---- multiple violations collected ----

class TestSimulationStateViolationCollection:
    """Constitution rule 23: collect all safely observable violations."""

    def test_multiple_violations_collected(self) -> None:
        """Bad element types, duplicate IDs, and dangling refs all collected."""
        acct = _make_account()
        with pytest.raises(InvalidRequestError) as exc_info:
            SimulationState.create_validated(
                (acct, acct),  # duplicate ID
                ("bad-sub",),  # bad element type + dangling ref
                (42,),         # bad element type + dangling ref
            )
        # Should see at least: duplicate accounts, bad subscriber
        # element, bad subscription element
        assert len(exc_info.value.violations) >= 3

    def test_is_valid_false_for_bad_state(self) -> None:
        """is_valid() returns False for a structurally invalid state."""
        acct = _make_account()
        # Direct construction bypasses create_validated.
        state = SimulationState(
            accounts=(acct, acct), subscribers=(), subscriptions=(),
        )
        assert not state.is_valid()
