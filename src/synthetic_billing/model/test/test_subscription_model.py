"""Tests for synthetic_billing.model.subscription_model."""

import pytest

from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    ENDED_SUBSCRIPTION_STATUS,
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.model.catalog_model import (
    build_catalog,
    build_feature,
    build_plan,
)
from synthetic_billing.model.subscription_model import (
    build_feature_subscription,
    build_plan_subscription,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _catalog() -> Catalog:
    """Build a catalog with two plans and one feature for testing."""
    return build_catalog(
        plans=[
            build_plan("BASIC", "Basic Plan", "9.99"),
            build_plan("PREMIUM", "Premium Plan", "19.99"),
        ],
        features=[
            build_feature("HD", "HD Audio", "2.99", ("BASIC", "PREMIUM")),
            build_feature("DVR", "Cloud DVR", "4.99", ("PREMIUM",)),
        ],
    )


# ---------------------------------------------------------------------------
# build_plan_subscription
# ---------------------------------------------------------------------------


class TestBuildPlanSubscriptionHappyPath:
    """build_plan_subscription constructs a valid plan Subscription."""

    def test_returns_subscription(self) -> None:
        """The return type is Subscription with item_type 'plan'."""
        sub = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=1, catalog=_catalog(),
        )
        assert isinstance(sub, Subscription)
        assert sub.item_type == PLAN_ITEM_TYPE
        assert sub.item_code == "BASIC"

    def test_default_active_status(self) -> None:
        """Omitting subscription_status defaults to active."""
        sub = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=1, catalog=_catalog(),
        )
        assert sub.subscription_status == ACTIVE_SUBSCRIPTION_STATUS
        assert sub.end_month is None

    def test_ended_subscription(self) -> None:
        """An ended plan subscription stores end_month and ended status."""
        sub = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC", start_month=1,
            catalog=_catalog(), end_month=6,
            subscription_status=ENDED_SUBSCRIPTION_STATUS,
        )
        assert sub.end_month == 6
        assert sub.subscription_status == ENDED_SUBSCRIPTION_STATUS


class TestBuildPlanSubscriptionIdDerivation:
    """Plan subscription IDs are deterministic per D28."""

    def test_id_matches_derive_id(self) -> None:
        """The subscription_id matches a direct derive_id call."""
        sub = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=3, catalog=_catalog(),
        )
        expected = derive_id("subscription", "sub001", "plan", "BASIC", 3)
        assert sub.subscription_id == expected

    def test_deterministic_across_calls(self) -> None:
        """Identical inputs produce the same subscription_id."""
        cat = _catalog()
        first = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=1, catalog=cat,
        )
        second = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=1, catalog=cat,
        )
        assert first.subscription_id == second.subscription_id

    def test_different_plan_different_id(self) -> None:
        """Different plan codes produce different subscription IDs."""
        cat = _catalog()
        basic = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=1, catalog=cat,
        )
        premium = build_plan_subscription(
            subscriber_id="sub001", plan_code="PREMIUM",
            start_month=1, catalog=cat,
        )
        assert basic.subscription_id != premium.subscription_id

    def test_different_month_different_id(self) -> None:
        """Different start months produce different subscription IDs."""
        cat = _catalog()
        early = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=1, catalog=cat,
        )
        late = build_plan_subscription(
            subscriber_id="sub001", plan_code="BASIC",
            start_month=5, catalog=cat,
        )
        assert early.subscription_id != late.subscription_id


class TestBuildPlanSubscriptionValidation:
    """build_plan_subscription validates structurally before checking catalog."""

    def test_rejects_missing_plan_code(self) -> None:
        """A plan_code not in the catalog raises ValueError."""
        with pytest.raises(ValueError, match="plan_code.*not found"):
            build_plan_subscription(
                subscriber_id="sub001", plan_code="GOLD",
                start_month=1, catalog=_catalog(),
            )

    def test_structural_fires_before_semantic(self) -> None:
        """A bad start_month fails before semantic catalog validation."""
        with pytest.raises(TypeError, match="bool"):
            build_plan_subscription(
                subscriber_id="sub001", plan_code="NONEXISTENT",
                start_month=True, catalog=_catalog(),
            )


# ---------------------------------------------------------------------------
# build_feature_subscription
# ---------------------------------------------------------------------------


class TestBuildFeatureSubscriptionHappyPath:
    """build_feature_subscription constructs a valid feature Subscription."""

    def test_returns_subscription(self) -> None:
        """The return type is Subscription with item_type 'feature'."""
        sub = build_feature_subscription(
            subscriber_id="sub001", feature_code="HD",
            plan_code="BASIC", start_month=1, catalog=_catalog(),
        )
        assert isinstance(sub, Subscription)
        assert sub.item_type == FEATURE_ITEM_TYPE
        assert sub.item_code == "HD"

    def test_premium_only_feature(self) -> None:
        """A feature restricted to PREMIUM works with plan_code PREMIUM."""
        sub = build_feature_subscription(
            subscriber_id="sub001", feature_code="DVR",
            plan_code="PREMIUM", start_month=1, catalog=_catalog(),
        )
        assert sub.item_code == "DVR"


class TestBuildFeatureSubscriptionIdDerivation:
    """Feature subscription IDs are deterministic per D28."""

    def test_id_matches_derive_id(self) -> None:
        """The subscription_id matches a direct derive_id call."""
        sub = build_feature_subscription(
            subscriber_id="sub001", feature_code="HD",
            plan_code="BASIC", start_month=2, catalog=_catalog(),
        )
        expected = derive_id("subscription", "sub001", "feature", "HD", 2)
        assert sub.subscription_id == expected

    def test_deterministic_across_calls(self) -> None:
        """Identical inputs produce the same subscription_id."""
        cat = _catalog()
        first = build_feature_subscription(
            subscriber_id="sub001", feature_code="HD",
            plan_code="BASIC", start_month=1, catalog=cat,
        )
        second = build_feature_subscription(
            subscriber_id="sub001", feature_code="HD",
            plan_code="BASIC", start_month=1, catalog=cat,
        )
        assert first.subscription_id == second.subscription_id

    def test_different_feature_different_id(self) -> None:
        """Different feature codes produce different subscription IDs."""
        cat = _catalog()
        hd = build_feature_subscription(
            subscriber_id="sub001", feature_code="HD",
            plan_code="PREMIUM", start_month=1, catalog=cat,
        )
        dvr = build_feature_subscription(
            subscriber_id="sub001", feature_code="DVR",
            plan_code="PREMIUM", start_month=1, catalog=cat,
        )
        assert hd.subscription_id != dvr.subscription_id


class TestBuildFeatureSubscriptionSemanticValidation:
    """build_feature_subscription validates feature, plan, and compatibility."""

    def test_rejects_missing_feature_code(self) -> None:
        """A feature_code not in the catalog raises ValueError."""
        with pytest.raises(ValueError, match="feature_code.*not found"):
            build_feature_subscription(
                subscriber_id="sub001", feature_code="SURROUND",
                plan_code="BASIC", start_month=1, catalog=_catalog(),
            )

    def test_rejects_missing_plan_code(self) -> None:
        """A plan_code not in the catalog raises ValueError."""
        with pytest.raises(ValueError, match="plan_code.*not found"):
            build_feature_subscription(
                subscriber_id="sub001", feature_code="HD",
                plan_code="GOLD", start_month=1, catalog=_catalog(),
            )

    def test_rejects_incompatible_plan(self) -> None:
        """A feature not compatible with the given plan raises ValueError."""
        with pytest.raises(ValueError, match="not compatible"):
            build_feature_subscription(
                subscriber_id="sub001", feature_code="DVR",
                plan_code="BASIC", start_month=1, catalog=_catalog(),
            )
