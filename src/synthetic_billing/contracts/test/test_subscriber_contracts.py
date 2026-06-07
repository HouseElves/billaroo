"""Tests for synthetic_billing.contracts.subscriber_contracts."""

import dataclasses

import pytest

from synthetic_billing.contracts.subscriber_contracts import Subscriber


def _subscriber(**overrides) -> Subscriber:
    """Build a valid Subscriber with defaults, applying *overrides*."""
    defaults = {
        "subscriber_id": "sub001",
        "account_id": "acct001",
        "subscriber_ordinal": 0,
        "plan_code": "BASIC",
        "active": True,
    }
    return Subscriber(**{**defaults, **overrides})


class TestSubscriberHappyPath:
    """Subscriber stores validated fields in a frozen dataclass."""

    def test_constructs_with_defaults(self) -> None:
        """All fields are stored unchanged."""
        sub = _subscriber()
        assert sub.subscriber_id == "sub001"
        assert sub.account_id == "acct001"
        assert sub.subscriber_ordinal == 0
        assert sub.plan_code == "BASIC"
        assert sub.active is True

    def test_inactive_subscriber(self) -> None:
        """An inactive subscriber is valid."""
        sub = _subscriber(active=False)
        assert sub.active is False

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        sub = _subscriber()
        with pytest.raises(dataclasses.FrozenInstanceError):
            sub.active = False  # type: ignore[misc]


class TestSubscriberIdValidation:
    """Subscriber rejects invalid subscriber_id values."""

    def test_rejects_non_string(self) -> None:
        """An integer subscriber_id is not a string."""
        with pytest.raises(TypeError, match="subscriber_id"):
            _subscriber(subscriber_id=42)

    def test_rejects_blank(self) -> None:
        """An empty subscriber_id is blank."""
        with pytest.raises(ValueError, match="subscriber_id"):
            _subscriber(subscriber_id="")


class TestSubscriberAccountIdValidation:
    """Subscriber rejects invalid account_id values."""

    def test_rejects_non_string(self) -> None:
        """An integer account_id is not a string."""
        with pytest.raises(TypeError, match="account_id"):
            _subscriber(account_id=42)

    def test_rejects_blank(self) -> None:
        """A whitespace-only account_id is blank."""
        with pytest.raises(ValueError, match="account_id"):
            _subscriber(account_id="   ")


class TestSubscriberOrdinalValidation:
    """Subscriber rejects invalid subscriber_ordinal values."""

    def test_rejects_bool(self) -> None:
        """Bool is rejected despite being an int subclass."""
        with pytest.raises(TypeError, match="subscriber_ordinal"):
            _subscriber(subscriber_ordinal=True)

    def test_rejects_float(self) -> None:
        """Float is not a valid ordinal."""
        with pytest.raises(TypeError, match="subscriber_ordinal"):
            _subscriber(subscriber_ordinal=1.0)

    def test_rejects_negative(self) -> None:
        """Negative ordinals are invalid."""
        with pytest.raises(ValueError, match="subscriber_ordinal"):
            _subscriber(subscriber_ordinal=-1)


class TestSubscriberPlanCodeValidation:
    """Subscriber rejects invalid plan_code values."""

    def test_rejects_non_string(self) -> None:
        """An integer plan_code is not a string."""
        with pytest.raises(TypeError, match="plan_code"):
            _subscriber(plan_code=42)

    def test_rejects_blank(self) -> None:
        """An empty plan_code is blank."""
        with pytest.raises(ValueError, match="plan_code"):
            _subscriber(plan_code="")


class TestSubscriberActiveValidation:
    """Subscriber rejects non-bool active values."""

    def test_rejects_int(self) -> None:
        """An integer 1 is not a bool."""
        with pytest.raises(TypeError, match="active"):
            _subscriber(active=1)

    def test_rejects_none(self) -> None:
        """None is not a bool."""
        with pytest.raises(TypeError, match="active"):
            _subscriber(active=None)

    def test_rejects_string(self) -> None:
        """A string is not a bool."""
        with pytest.raises(TypeError, match="active"):
            _subscriber(active="true")
