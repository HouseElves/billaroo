"""Tests for synthetic_billing.contracts.catalog_contracts."""

import dataclasses
from decimal import Decimal

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.contracts.catalog_contracts import (
    Catalog,
    FeatureDefinition,
    PlanDefinition,
)
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan(
    code: str = "BASIC",
    display: str = "Basic Plan",
    price: str = "9.99",
) -> PlanDefinition:
    """Build a valid PlanDefinition via create_validated."""
    return PlanDefinition.create_validated(code, display, Decimal(price))


def _feature(
    code: str = "HD",
    display: str = "HD Audio",
    price: str = "2.99",
    allowed: tuple[str, ...] = ("BASIC",),
) -> FeatureDefinition:
    """Build a valid FeatureDefinition via create_validated."""
    return FeatureDefinition.create_validated(
        code, display, Decimal(price), allowed,
    )


# ---------------------------------------------------------------------------
# PlanDefinition
# ---------------------------------------------------------------------------


class TestPlanDefinitionHappyPath:
    """PlanDefinition stores validated fields in a frozen dataclass."""

    def test_is_validated_subclass(self) -> None:
        """PlanDefinition inherits from _Validated."""
        assert issubclass(PlanDefinition, _Validated)

    def test_constructs(self) -> None:
        """All fields are stored unchanged."""
        plan = _plan()
        assert plan.plan_code == "BASIC"
        assert plan.display_name == "Basic Plan"
        assert plan.monthly_price == Decimal("9.99")

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        plan = _plan()
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.plan_code = "PREMIUM"  # type: ignore[misc]

    def test_validate_happy_path(self) -> None:
        """validate() on a valid plan returns None."""
        assert _plan().validate() is None

    def test_is_valid_true(self) -> None:
        """is_valid() is True for a structurally valid plan."""
        assert _plan().is_valid() is True


class TestPlanDefinitionTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_non_string_code(self) -> None:
        """An integer plan_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            PlanDefinition.create_validated(42, "Basic", Decimal("9.99"))
        assert ("plan_code", 42) in exc_info.value.violations

    def test_non_string_display_name(self) -> None:
        """An integer display_name is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            PlanDefinition.create_validated("BASIC", 42, Decimal("9.99"))
        assert ("display_name", 42) in exc_info.value.violations

    def test_non_decimal_price(self) -> None:
        """A float monthly_price is rejected (use build_money)."""
        with pytest.raises(InvalidRequestError) as exc_info:
            PlanDefinition.create_validated("BASIC", "Basic", 9.99)
        assert any(f == "monthly_price" for f, _ in exc_info.value.violations)


class TestPlanDefinitionStructuralChecks:
    """Structural validation catches blank values."""

    def test_blank_code(self) -> None:
        """A whitespace-only plan_code is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            PlanDefinition.create_validated("   ", "Basic", Decimal("9.99"))
        assert any(f == "plan_code" for f, _ in exc_info.value.violations)

    def test_blank_display_name(self) -> None:
        """An empty display_name is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            PlanDefinition.create_validated("BASIC", "", Decimal("9.99"))
        assert any(f == "display_name" for f, _ in exc_info.value.violations)

    def test_is_valid_false(self) -> None:
        """Direct construction with blank code yields is_valid()=False."""
        plan = PlanDefinition(
            plan_code=" ", display_name="X", monthly_price=Decimal("1.00"),
        )
        assert plan.is_valid() is False


# ---------------------------------------------------------------------------
# FeatureDefinition
# ---------------------------------------------------------------------------


class TestFeatureDefinitionHappyPath:
    """FeatureDefinition stores validated fields in a frozen dataclass."""

    def test_is_validated_subclass(self) -> None:
        """FeatureDefinition inherits from _Validated."""
        assert issubclass(FeatureDefinition, _Validated)

    def test_constructs(self) -> None:
        """All fields including allowed_plan_codes are stored."""
        feature = _feature(allowed=("BASIC", "PREMIUM"))
        assert feature.allowed_plan_codes == ("BASIC", "PREMIUM")

    def test_validity_check_true(self) -> None:
        """validity_check returns (True, name, instance) when valid."""
        feature = _feature()
        passed, name, obj = feature.validity_check("feat")
        assert passed is True
        assert name == "feat"
        assert obj is feature


class TestFeatureDefinitionTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_non_string_code(self) -> None:
        """An integer feature_code is rejected."""
        with pytest.raises(InvalidRequestError):
            FeatureDefinition.create_validated(
                42, "HD", Decimal("2.99"), ("BASIC",),
            )

    def test_non_string_display_name(self) -> None:
        """An integer display_name is rejected."""
        with pytest.raises(InvalidRequestError):
            FeatureDefinition.create_validated(
                "HD", 42, Decimal("2.99"), ("BASIC",),
            )

    def test_non_decimal_price(self) -> None:
        """A float monthly_price is rejected."""
        with pytest.raises(InvalidRequestError):
            FeatureDefinition.create_validated(
                "HD", "HD", 2.99, ("BASIC",),
            )

    def test_non_tuple_allowed_plan_codes(self) -> None:
        """A list of allowed_plan_codes is rejected (must be tuple)."""
        with pytest.raises(InvalidRequestError):
            FeatureDefinition.create_validated(
                "HD", "HD", Decimal("2.99"), ["BASIC"],
            )


class TestFeatureDefinitionStructuralChecks:
    """Structural validation catches blank values and empty allowed list."""

    def test_blank_code(self) -> None:
        """An empty feature_code is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            FeatureDefinition.create_validated(
                "", "HD", Decimal("2.99"), ("BASIC",),
            )
        assert any(f == "feature_code" for f, _ in exc_info.value.violations)

    def test_blank_display_name(self) -> None:
        """An empty display_name is structurally invalid."""
        with pytest.raises(InvalidRequestError) as exc_info:
            FeatureDefinition.create_validated(
                "HD", "", Decimal("2.99"), ("BASIC",),
            )
        assert any(f == "display_name" for f, _ in exc_info.value.violations)

    def test_empty_allowed_plan_codes_rejected(self) -> None:
        """An empty allowed_plan_codes tuple is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            FeatureDefinition.create_validated(
                "HD", "HD", Decimal("2.99"), (),
            )
        assert any(
            f == "allowed_plan_codes" for f, _ in exc_info.value.violations
        )

    def test_blank_allowed_plan_code_element(self) -> None:
        """An empty string inside allowed_plan_codes is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            FeatureDefinition.create_validated(
                "HD", "HD", Decimal("2.99"), ("BASIC", ""),
            )
        assert any(
            "allowed_plan_codes" in f for f, _ in exc_info.value.violations
        )

    def test_non_string_allowed_plan_code_element(self) -> None:
        """A non-string element inside allowed_plan_codes is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            FeatureDefinition.create_validated(
                "HD", "HD", Decimal("2.99"), ("BASIC", 42),
            )
        assert any(
            "allowed_plan_codes" in f for f, _ in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class TestCatalogHappyPath:
    """Catalog stores validated tuples of plans and features."""

    def test_is_validated_subclass(self) -> None:
        """Catalog inherits from _Validated."""
        assert issubclass(Catalog, _Validated)

    def test_constructs_with_plans_and_features(self) -> None:
        """A catalog with cross-referenced plans and features is valid."""
        catalog = Catalog.create_validated(
            (_plan("BASIC"), _plan("PREMIUM", "Premium")),
            (_feature("HD", allowed=("BASIC", "PREMIUM")),),
        )
        assert len(catalog.plans) == 2
        assert len(catalog.features) == 1

    def test_constructs_with_plans_only(self) -> None:
        """A catalog with plans and no features is valid."""
        catalog = Catalog.create_validated((_plan(),), ())
        assert len(catalog.plans) == 1
        assert not catalog.features

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        catalog = Catalog.create_validated((_plan(),), ())
        with pytest.raises(dataclasses.FrozenInstanceError):
            catalog.plans = ()  # type: ignore[misc]


class TestCatalogTypeChecks:
    """create_validated rejects non-tuple plans or features."""

    def test_non_tuple_plans(self) -> None:
        """A list of plans is rejected."""
        with pytest.raises(InvalidRequestError):
            Catalog.create_validated([_plan()], ())

    def test_non_tuple_features(self) -> None:
        """A list of features is rejected."""
        with pytest.raises(InvalidRequestError):
            Catalog.create_validated((_plan(),), [])


class TestCatalogStructuralChecks:
    """Catalog enforces non-empty plans, unique codes, and resolved refs."""

    def test_empty_plans_rejected(self) -> None:
        """A catalog with no plans is rejected (at least one required)."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated((), ())
        assert any(f == "plans" for f, _ in exc_info.value.violations)

    def test_duplicate_plan_codes(self) -> None:
        """Two plans with the same code are rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated((_plan("BASIC"), _plan("BASIC")), ())
        assert any(f == "plans" for f, _ in exc_info.value.violations)

    def test_duplicate_feature_codes(self) -> None:
        """Two features with the same code are rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(
                (_plan("BASIC"),),
                (_feature("HD", allowed=("BASIC",)),
                 _feature("HD", allowed=("BASIC",))),
            )
        assert any(f == "features" for f, _ in exc_info.value.violations)

    def test_dangling_feature_plan_reference(self) -> None:
        """A feature referencing a missing plan code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(
                (_plan("BASIC"),),
                (_feature("HD", allowed=("PREMIUM",)),),
            )
        field_names = {f for f, _ in exc_info.value.violations}
        assert any("allowed_plan_codes" in f for f in field_names)

    def test_non_plan_element_rejected(self) -> None:
        """A non-PlanDefinition element in plans is reported as a violation."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(("not-a-plan",), ())
        assert ("plans[0]", "not-a-plan") in exc_info.value.violations

    def test_non_feature_element_rejected(self) -> None:
        """A non-FeatureDefinition element in features is reported."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated((_plan(),), ("not-a-feature",))
        assert ("features[0]", "not-a-feature") in exc_info.value.violations

    def test_bad_plan_and_bad_feature_both_collected(self) -> None:
        """Both bad-plan and bad-feature violations are collected together."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(("bad-plan",), ("bad-feature",))
        assert ("plans[0]", "bad-plan") in exc_info.value.violations
        assert ("features[0]", "bad-feature") in exc_info.value.violations

    def test_bad_elements_do_not_raise_attribute_error(self) -> None:
        """Wrong element types produce InvalidRequestError, not AttributeError."""
        catalog = Catalog(plans=("not-a-plan",), features=("not-a-feature",))
        assert catalog.is_valid() is False

    def test_bad_plan_and_duplicate_valid_plans_both_collected(self) -> None:
        """A bad element and duplicate valid plan codes are both reported."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(
                ("bad", _plan("A"), _plan("A")),
                (),
            )
        violations = exc_info.value.violations
        assert ("plans[0]", "bad") in violations
        assert any(f == "plans" for f, _ in violations)

    def test_bad_feature_and_duplicate_valid_features_both_collected(self) -> None:
        """A bad element and duplicate valid feature codes are both reported."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(
                (_plan("A"),),
                ("bad", _feature("X", allowed=("A",)),
                 _feature("X", allowed=("A",))),
            )
        violations = exc_info.value.violations
        assert ("features[0]", "bad") in violations
        assert any(f == "features" for f, _ in violations)

    def test_bad_elements_do_not_prevent_cross_ref_checks(self) -> None:
        """Cross-ref checks run on valid features against valid plan codes."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(
                (_plan("A"), "bad-plan"),
                (_feature("X", allowed=("MISSING",)),),
            )
        violations = exc_info.value.violations
        assert ("plans[1]", "bad-plan") in violations
        assert any("allowed_plan_codes" in f for f, _ in violations)

    def test_multiple_violations_collected(self) -> None:
        """Duplicate plans AND dangling reference are reported together."""
        with pytest.raises(InvalidRequestError) as exc_info:
            Catalog.create_validated(
                (_plan("BASIC"), _plan("BASIC")),
                (_feature("HD", allowed=("PREMIUM",)),),
            )
        field_names = {f for f, _ in exc_info.value.violations}
        assert "plans" in field_names
        assert any("allowed_plan_codes" in f for f in field_names)
