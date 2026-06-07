"""Tests for synthetic_billing.contracts.catalog_contracts."""

import dataclasses
from decimal import Decimal

import pytest

from synthetic_billing.contracts.catalog_contracts import (
    Catalog,
    FeatureDefinition,
    PlanDefinition,
)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class TestPlanDefinitionHappyPath:
    """PlanDefinition holds a validated plan code, name, and Decimal price."""

    def test_constructs(self) -> None:
        """All fields are stored unchanged."""
        plan = PlanDefinition(
            plan_code="BASIC",
            plan_name="Basic Plan",
            monthly_price=Decimal("9.99"),
        )
        assert plan.plan_code == "BASIC"
        assert plan.monthly_price == Decimal("9.99")

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        plan = PlanDefinition("BASIC", "Basic", Decimal("9.99"))
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.plan_code = "PREMIUM"  # type: ignore[misc]


class TestPlanDefinitionValidation:
    """PlanDefinition rejects non-string codes, blank values, and non-Decimal prices."""

    def test_rejects_non_string_code(self) -> None:
        """An integer plan_code is not a string."""
        with pytest.raises(TypeError, match="plan_code"):
            PlanDefinition(
                plan_code=42,  # type: ignore[arg-type]
                plan_name="Basic",
                monthly_price=Decimal("9.99"),
            )

    def test_rejects_blank_code(self) -> None:
        """A whitespace-only plan_code is blank."""
        with pytest.raises(ValueError, match="plan_code"):
            PlanDefinition("   ", "Basic", Decimal("9.99"))

    def test_rejects_non_string_name(self) -> None:
        """An integer plan_name is not a string."""
        with pytest.raises(TypeError, match="plan_name"):
            PlanDefinition(
                plan_code="BASIC",
                plan_name=42,  # type: ignore[arg-type]
                monthly_price=Decimal("9.99"),
            )

    def test_rejects_blank_name(self) -> None:
        """An empty plan_name is blank."""
        with pytest.raises(ValueError, match="plan_name"):
            PlanDefinition("BASIC", "", Decimal("9.99"))

    def test_rejects_non_decimal_price(self) -> None:
        """A float monthly_price is not a Decimal."""
        with pytest.raises(TypeError, match="monthly_price"):
            PlanDefinition(
                plan_code="BASIC",
                plan_name="Basic",
                monthly_price=9.99,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------


class TestFeatureDefinitionHappyPath:
    """FeatureDefinition holds a code, name, price, and allowed plan codes."""

    def test_constructs(self) -> None:
        """All fields including the plan-code tuple are stored."""
        feature = FeatureDefinition(
            feature_code="HD",
            feature_name="HD Audio",
            monthly_price=Decimal("2.99"),
            allowed_plan_codes=("BASIC", "PREMIUM"),
        )
        assert feature.allowed_plan_codes == ("BASIC", "PREMIUM")

    def test_empty_allowed_plan_codes_is_valid_shape(self) -> None:
        """An empty tuple is structurally valid; semantic rules live elsewhere."""
        feature = FeatureDefinition(
            "HD", "HD Audio", Decimal("2.99"), ()
        )
        assert not feature.allowed_plan_codes


class TestFeatureDefinitionValidation:
    """FeatureDefinition rejects blank codes, non-Decimal prices, and malformed plan code tuples."""

    def test_rejects_blank_code(self) -> None:
        """An empty feature_code is blank."""
        with pytest.raises(ValueError, match="feature_code"):
            FeatureDefinition("", "HD", Decimal("2.99"), ("BASIC",))

    def test_rejects_non_string_code(self) -> None:
        """An integer feature_code is not a string."""
        with pytest.raises(TypeError, match="feature_code"):
            FeatureDefinition(
                42,  # type: ignore[arg-type]
                "HD",
                Decimal("2.99"),
                ("BASIC",),
            )

    def test_rejects_blank_name(self) -> None:
        """An empty feature_name is blank."""
        with pytest.raises(ValueError, match="feature_name"):
            FeatureDefinition("HD", "", Decimal("2.99"), ("BASIC",))

    def test_rejects_non_string_name(self) -> None:
        """An integer feature_name is not a string."""
        with pytest.raises(TypeError, match="feature_name"):
            FeatureDefinition(
                "HD",
                42,  # type: ignore[arg-type]
                Decimal("2.99"),
                ("BASIC",),
            )

    def test_rejects_non_decimal_price(self) -> None:
        """A float monthly_price is not a Decimal."""
        with pytest.raises(TypeError, match="monthly_price"):
            FeatureDefinition(
                "HD", "HD", 2.99, ("BASIC",)  # type: ignore[arg-type]
            )

    def test_rejects_non_tuple_allowed_plan_codes(self) -> None:
        """A list is not a tuple."""
        with pytest.raises(TypeError, match="allowed_plan_codes"):
            FeatureDefinition(
                "HD",
                "HD",
                Decimal("2.99"),
                ["BASIC"],  # type: ignore[arg-type]
            )

    def test_rejects_blank_allowed_plan_code(self) -> None:
        """An empty string inside allowed_plan_codes is blank."""
        with pytest.raises(ValueError, match="allowed_plan_codes"):
            FeatureDefinition("HD", "HD", Decimal("2.99"), ("BASIC", ""))

    def test_rejects_non_string_allowed_plan_code(self) -> None:
        """An integer inside allowed_plan_codes is not a string."""
        with pytest.raises(TypeError, match="allowed_plan_codes"):
            FeatureDefinition(
                "HD",
                "HD",
                Decimal("2.99"),
                ("BASIC", 42),  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def _plan(code: str, price: str = "9.99") -> PlanDefinition:
    """Build a minimal PlanDefinition for test convenience."""
    return PlanDefinition(code, f"Plan {code}", Decimal(price))


def _feature(
    code: str,
    allowed: tuple[str, ...],
    price: str = "2.99",
) -> FeatureDefinition:
    """Build a minimal FeatureDefinition for test convenience."""
    return FeatureDefinition(code, f"Feature {code}", Decimal(price), allowed)


class TestCatalogHappyPath:
    """Catalog holds validated tuples of plans and features."""

    def test_constructs_with_plans_and_features(self) -> None:
        """A catalog with cross-referenced plans and features is valid."""
        catalog = Catalog(
            plans=(_plan("BASIC"), _plan("PREMIUM")),
            features=(_feature("HD", ("BASIC", "PREMIUM")),),
        )
        assert len(catalog.plans) == 2
        assert len(catalog.features) == 1

    def test_empty_catalog_is_valid(self) -> None:
        """No plans and no features is structurally well-formed."""
        catalog = Catalog(plans=(), features=())
        assert not catalog.plans
        assert not catalog.features

    def test_features_without_plans_only_valid_if_no_refs(self) -> None:
        """A feature with an empty allowed_plan_codes needs no plans."""
        catalog = Catalog(plans=(), features=(_feature("HD", ()),))
        assert len(catalog.features) == 1


class TestCatalogValidation:
    """Catalog rejects duplicate codes, dangling feature references, and non-tuple inputs."""

    def test_rejects_non_tuple_plans(self) -> None:
        """A list of plans is not a tuple."""
        with pytest.raises(TypeError, match="plans"):
            Catalog(
                plans=[_plan("BASIC")],  # type: ignore[arg-type]
                features=(),
            )

    def test_rejects_non_tuple_features(self) -> None:
        """A list of features is not a tuple."""
        with pytest.raises(TypeError, match="features"):
            Catalog(
                plans=(_plan("BASIC"),),
                features=[],  # type: ignore[arg-type]
            )

    def test_rejects_duplicate_plan_codes(self) -> None:
        """Two plans with the same code are rejected."""
        with pytest.raises(ValueError, match="duplicate plan_code"):
            Catalog(
                plans=(_plan("BASIC"), _plan("BASIC")),
                features=(),
            )

    def test_rejects_duplicate_feature_codes(self) -> None:
        """Two features with the same code are rejected."""
        with pytest.raises(ValueError, match="duplicate feature_code"):
            Catalog(
                plans=(_plan("BASIC"),),
                features=(
                    _feature("HD", ("BASIC",)),
                    _feature("HD", ("BASIC",)),
                ),
            )

    def test_rejects_feature_referencing_unknown_plan(self) -> None:
        """A feature whose allowed_plan_codes entry has no matching plan is rejected."""
        with pytest.raises(ValueError, match="unknown plan_code"):
            Catalog(
                plans=(_plan("BASIC"),),
                features=(_feature("HD", ("PREMIUM",)),),
            )

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        catalog = Catalog(plans=(), features=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            catalog.plans = (_plan("BASIC"),)  # type: ignore[misc]
