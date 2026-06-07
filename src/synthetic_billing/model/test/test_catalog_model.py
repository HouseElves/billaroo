"""Tests for synthetic_billing.model.catalog_model."""

from decimal import Decimal

import pytest

from synthetic_billing.contracts.catalog_contracts import (
    Catalog,
    FeatureDefinition,
    PlanDefinition,
)
from synthetic_billing.model.catalog_model import (
    build_catalog,
    build_feature,
    build_plan,
)


class TestBuildPlan:
    """build_plan routes prices through build_money and returns a PlanDefinition."""

    def test_from_str_price(self) -> None:
        """A string price is parsed to Decimal via build_money."""
        plan = build_plan("BASIC", "Basic Plan", "9.99")
        assert isinstance(plan, PlanDefinition)
        assert plan.monthly_price == Decimal("9.99")

    def test_from_int_price(self) -> None:
        """An integer price is quantized to cents."""
        plan = build_plan("BASIC", "Basic Plan", 10)
        assert plan.monthly_price == Decimal("10.00")

    def test_from_decimal_price(self) -> None:
        """A Decimal price passes through unchanged."""
        plan = build_plan("BASIC", "Basic Plan", Decimal("9.99"))
        assert plan.monthly_price == Decimal("9.99")

    def test_quantizes_price(self) -> None:
        """Sub-cent precision is rounded by build_money."""
        plan = build_plan("BASIC", "Basic Plan", "9.999")
        assert plan.monthly_price == Decimal("10.00")

    def test_rejects_float_price(self) -> None:
        """Float rejection fires at the build_money boundary."""
        with pytest.raises(TypeError, match="float"):
            build_plan("BASIC", "Basic Plan", 9.99)  # type: ignore[arg-type]

    def test_rejects_blank_code(self) -> None:
        """A blank plan_code is rejected by the PlanDefinition contract."""
        with pytest.raises(ValueError, match="plan_code"):
            build_plan("", "Basic Plan", "9.99")


class TestBuildFeature:
    """build_feature materializes allowed_plan_codes to a tuple and validates price."""

    def test_with_tuple_allowed_codes(self) -> None:
        """A tuple of plan codes passes through unchanged."""
        feature = build_feature("HD", "HD Audio", "2.99", ("BASIC",))
        assert isinstance(feature, FeatureDefinition)
        assert feature.allowed_plan_codes == ("BASIC",)

    def test_with_list_allowed_codes(self) -> None:
        """A list is materialized to a tuple."""
        feature = build_feature("HD", "HD Audio", "2.99", ["BASIC", "PREMIUM"])
        assert feature.allowed_plan_codes == ("BASIC", "PREMIUM")

    def test_with_generator_allowed_codes(self) -> None:
        """A generator is materialized to a tuple."""
        feature = build_feature(
            "HD", "HD Audio", "2.99", (c for c in ["BASIC"])
        )
        assert feature.allowed_plan_codes == ("BASIC",)

    def test_rejects_float_price(self) -> None:
        """Float rejection fires at the build_money boundary."""
        with pytest.raises(TypeError, match="float"):
            build_feature(
                "HD", "HD Audio", 2.99, ("BASIC",)  # type: ignore[arg-type]
            )


class TestBuildCatalog:
    """build_catalog assembles a validated Catalog from plan and feature iterables."""

    def test_constructs_catalog(self) -> None:
        """Plans and features are stored as tuples inside the Catalog."""
        plans = [build_plan("BASIC", "Basic", "9.99")]
        features = [build_feature("HD", "HD Audio", "2.99", ("BASIC",))]
        catalog = build_catalog(plans, features)
        assert isinstance(catalog, Catalog)
        assert len(catalog.plans) == 1
        assert len(catalog.features) == 1

    def test_accepts_generators(self) -> None:
        """Generator iterables are materialized into the catalog tuples."""
        plans_gen = (build_plan(c, f"P{c}", "9.99") for c in ["A", "B"])
        features_gen = (build_feature(c, f"F{c}", "1.00", ("A",)) for c in ["X"])
        catalog = build_catalog(plans_gen, features_gen)
        assert {p.plan_code for p in catalog.plans} == {"A", "B"}

    def test_empty_catalog(self) -> None:
        """An empty catalog has no plans and no features."""
        catalog = build_catalog([], [])
        assert not catalog.plans
        assert not catalog.features

    def test_propagates_duplicate_plan_error(self) -> None:
        """Catalog.__post_init__ fires through build_catalog on duplicate plans."""
        plans = [
            build_plan("BASIC", "Basic", "9.99"),
            build_plan("BASIC", "Basic Again", "10.00"),
        ]
        with pytest.raises(ValueError, match="duplicate plan_code"):
            build_catalog(plans, [])

    def test_propagates_dangling_reference_error(self) -> None:
        """Catalog.__post_init__ fires through build_catalog on missing plan refs."""
        plans = [build_plan("BASIC", "Basic", "9.99")]
        features = [build_feature("HD", "HD", "2.99", ("PREMIUM",))]
        with pytest.raises(ValueError, match="unknown plan_code"):
            build_catalog(plans, features)

    def test_identical_inputs_equal_catalogs(self) -> None:
        """Determinism: identical construction inputs produce equal objects."""
        first = build_catalog(
            [build_plan("BASIC", "Basic", "9.99")],
            [build_feature("HD", "HD", "2.99", ("BASIC",))],
        )
        second = build_catalog(
            [build_plan("BASIC", "Basic", "9.99")],
            [build_feature("HD", "HD", "2.99", ("BASIC",))],
        )
        assert first == second
