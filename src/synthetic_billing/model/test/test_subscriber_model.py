"""Tests for synthetic_billing.model.subscriber_model."""

import pytest

from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.subscriber_contracts import Subscriber
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.catalog_model import build_catalog, build_plan
from synthetic_billing.model.subscriber_model import build_subscriber


def _catalog() -> Catalog:
    """Build a minimal catalog with BASIC and PREMIUM plans."""
    return build_catalog(
        plans=[
            build_plan("BASIC", "Basic Plan", "9.99"),
            build_plan("PREMIUM", "Premium Plan", "19.99"),
        ],
        features=[],
    )


class TestBuildSubscriberHappyPath:
    """build_subscriber derives a deterministic ID and returns a validated Subscriber."""

    def test_returns_subscriber(self) -> None:
        """The return type is Subscriber."""
        sub = build_subscriber(
            account_id="acct001", subscriber_ordinal=0,
            plan_code="BASIC", catalog=_catalog(),
        )
        assert isinstance(sub, Subscriber)

    def test_default_active_is_true(self) -> None:
        """Omitting active defaults to True."""
        sub = build_subscriber(
            account_id="acct001", subscriber_ordinal=0,
            plan_code="BASIC", catalog=_catalog(),
        )
        assert sub.active is True

    def test_explicit_inactive(self) -> None:
        """An explicit active=False is stored."""
        sub = build_subscriber(
            account_id="acct001", subscriber_ordinal=0,
            plan_code="BASIC", catalog=_catalog(), active=False,
        )
        assert sub.active is False

    def test_fields_stored(self) -> None:
        """Account ID, ordinal, and plan code are passed through."""
        sub = build_subscriber(
            account_id="acct001", subscriber_ordinal=3,
            plan_code="PREMIUM", catalog=_catalog(),
        )
        assert sub.account_id == "acct001"
        assert sub.subscriber_ordinal == 3
        assert sub.plan_code == "PREMIUM"


class TestBuildSubscriberIdDerivation:
    """build_subscriber derives subscriber_id via derive_id('subscriber', ...)."""

    def test_id_matches_derive_id(self) -> None:
        """The subscriber_id matches a direct derive_id call."""
        sub = build_subscriber(
            account_id="acct001", subscriber_ordinal=2,
            plan_code="BASIC", catalog=_catalog(),
        )
        expected = derive_id("subscriber", "acct001", 2)
        assert sub.subscriber_id == expected

    def test_deterministic_across_calls(self) -> None:
        """Identical inputs produce the same subscriber_id."""
        cat = _catalog()
        first = build_subscriber(
            account_id="acct001", subscriber_ordinal=0,
            plan_code="BASIC", catalog=cat,
        )
        second = build_subscriber(
            account_id="acct001", subscriber_ordinal=0,
            plan_code="BASIC", catalog=cat,
        )
        assert first.subscriber_id == second.subscriber_id

    def test_different_ordinals_different_ids(self) -> None:
        """Different subscriber ordinals produce different IDs."""
        cat = _catalog()
        a = build_subscriber(
            account_id="acct001", subscriber_ordinal=0,
            plan_code="BASIC", catalog=cat,
        )
        b = build_subscriber(
            account_id="acct001", subscriber_ordinal=1,
            plan_code="BASIC", catalog=cat,
        )
        assert a.subscriber_id != b.subscriber_id

    def test_different_accounts_different_ids(self) -> None:
        """Different parent accounts produce different subscriber IDs."""
        cat = _catalog()
        a = build_subscriber(
            account_id="acct001", subscriber_ordinal=0,
            plan_code="BASIC", catalog=cat,
        )
        b = build_subscriber(
            account_id="acct002", subscriber_ordinal=0,
            plan_code="BASIC", catalog=cat,
        )
        assert a.subscriber_id != b.subscriber_id


class TestBuildSubscriberCatalogValidation:
    """build_subscriber validates plan_code against the catalog (D15 boundary)."""

    def test_rejects_unknown_plan_code(self) -> None:
        """A plan code not in the catalog raises ValueError."""
        with pytest.raises(ValueError, match="plan_code.*not found"):
            build_subscriber(
                account_id="acct001", subscriber_ordinal=0,
                plan_code="GOLD", catalog=_catalog(),
            )

    def test_accepts_all_catalog_plans(self) -> None:
        """Every plan code in the catalog is accepted."""
        cat = _catalog()
        for plan in cat.plans:
            sub = build_subscriber(
                account_id="acct001", subscriber_ordinal=0,
                plan_code=plan.plan_code, catalog=cat,
            )
            assert sub.plan_code == plan.plan_code

    def test_error_message_lists_valid_codes(self) -> None:
        """The error for an unknown plan code includes the valid options."""
        with pytest.raises(ValueError, match="BASIC"):
            build_subscriber(
                account_id="acct001", subscriber_ordinal=0,
                plan_code="NONEXISTENT", catalog=_catalog(),
            )


class TestBuildSubscriberInputValidation:
    """build_subscriber rejects invalid inputs at the earliest validation boundary."""

    def test_rejects_blank_account_id(self) -> None:
        """A blank account_id is rejected during ID derivation."""
        with pytest.raises(ValueError, match="blank"):
            build_subscriber(
                account_id="", subscriber_ordinal=0,
                plan_code="BASIC", catalog=_catalog(),
            )

    def test_rejects_bool_ordinal(self) -> None:
        """A bool subscriber_ordinal is rejected during ID derivation."""
        with pytest.raises(TypeError, match="bool"):
            build_subscriber(
                account_id="acct001", subscriber_ordinal=True,
                plan_code="BASIC", catalog=_catalog(),
            )

    def test_rejects_non_bool_active(self) -> None:
        """A non-bool active is rejected by create_validated."""
        with pytest.raises(InvalidRequestError) as exc_info:
            build_subscriber(
                account_id="acct001", subscriber_ordinal=0,
                plan_code="BASIC", catalog=_catalog(),
                active=1,  # type: ignore[arg-type]
            )
        assert any(f == "active" for f, _ in exc_info.value.violations)
