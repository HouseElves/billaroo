"""Plan and feature catalog schemas.

Pure contract module: no I/O, no logging, no database, no pandas.

A plan is a subscription tier (Basic, Standard, Premium, ...) with a
monthly recurring price.  A feature is an optional add-on attachable
to one or more plans, also with a monthly recurring price.  A catalog
is the closed set of valid plans and features for a scenario; its
internal consistency (unique codes, feature-to-plan references resolve)
is enforced at construction time.

External semantic validation — "is this plan_code in *this* catalog?"
— belongs to the validate layer per design constitution rule 8.  The
checks here are the structural invariants without which a
``Catalog`` instance is malformed.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

__all__ = [
    "PlanDefinition",
    "FeatureDefinition",
    "Catalog",
]


def _validate_non_blank_code(name: str, value: object) -> None:
    """Check that *value* is a non-blank string."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


def _validate_decimal_price(name: str, value: object) -> None:
    """Check that *value* is a Decimal.

    Construction through ``catalog_model.build_plan`` /
    ``build_feature`` routes raw money inputs through ``build_money``,
    so by the time a definition reaches this contract layer the price
    must already be a ``Decimal``.
    """
    if not isinstance(value, Decimal):
        raise TypeError(
            f"{name} must be Decimal (use build_money), "
            f"got {type(value).__name__}"
        )


@dataclasses.dataclass(frozen=True)
class PlanDefinition:
    """A subscription plan tier.

    Attributes:
        plan_code: Short stable identifier (e.g. ``"BASIC"``).
        plan_name: Human-readable name.
        monthly_price: Recurring monthly price as a quantized Decimal.
    """

    plan_code: str
    plan_name: str
    monthly_price: Decimal

    def __post_init__(self) -> None:
        _validate_non_blank_code("plan_code", self.plan_code)
        _validate_non_blank_code("plan_name", self.plan_name)
        _validate_decimal_price("monthly_price", self.monthly_price)


@dataclasses.dataclass(frozen=True)
class FeatureDefinition:
    """An optional add-on feature attachable to one or more plans.

    Attributes:
        feature_code: Short stable identifier.
        feature_name: Human-readable name.
        monthly_price: Recurring monthly price as a quantized Decimal.
        allowed_plan_codes: Tuple of plan codes this feature may attach
            to.  Cross-reference resolution is enforced by ``Catalog``.
    """

    feature_code: str
    feature_name: str
    monthly_price: Decimal
    allowed_plan_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_blank_code("feature_code", self.feature_code)
        _validate_non_blank_code("feature_name", self.feature_name)
        _validate_decimal_price("monthly_price", self.monthly_price)
        if not isinstance(self.allowed_plan_codes, tuple):
            raise TypeError(
                "allowed_plan_codes must be a tuple, got "
                f"{type(self.allowed_plan_codes).__name__}"
            )
        for code in self.allowed_plan_codes:
            _validate_non_blank_code("allowed_plan_codes entry", code)


@dataclasses.dataclass(frozen=True)
class Catalog:
    """The closed set of plans and features for a scenario.

    Construction validates the internal invariants:

    - plan codes are unique
    - feature codes are unique
    - every ``allowed_plan_codes`` entry on every feature resolves to a
      plan in this catalog

    An empty catalog (no plans, no features) is structurally valid;
    semantic rules about whether a scenario *needs* plans live
    elsewhere.
    """

    plans: tuple[PlanDefinition, ...]
    features: tuple[FeatureDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plans, tuple):
            raise TypeError(
                f"plans must be a tuple, got {type(self.plans).__name__}"
            )
        if not isinstance(self.features, tuple):
            raise TypeError(
                f"features must be a tuple, got "
                f"{type(self.features).__name__}"
            )

        plan_codes = [p.plan_code for p in self.plans]
        if len(plan_codes) != len(set(plan_codes)):
            raise ValueError(
                f"duplicate plan_code in catalog: {sorted(plan_codes)}"
            )

        feature_codes = [f.feature_code for f in self.features]
        if len(feature_codes) != len(set(feature_codes)):
            raise ValueError(
                f"duplicate feature_code in catalog: {sorted(feature_codes)}"
            )

        plan_code_set = set(plan_codes)
        for feature in self.features:
            for code in feature.allowed_plan_codes:
                if code not in plan_code_set:
                    raise ValueError(
                        f"feature {feature.feature_code!r} references "
                        f"unknown plan_code {code!r}"
                    )
