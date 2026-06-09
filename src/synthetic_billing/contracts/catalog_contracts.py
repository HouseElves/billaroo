"""Plan and feature catalog schemas.

Pure contract module: no I/O, no logging, no database, no pandas, no
model-layer imports.

A plan is a subscription tier (Basic, Standard, Premium, ...) with a
monthly recurring price.  A feature is an optional add-on attachable
to one or more plans, also with a monthly recurring price.  A catalog
is the closed set of valid plans and features for a scenario; its
internal consistency (non-empty plan set, unique codes, feature-to-plan
references resolve) is enforced at construction time via
``_Validated.create_validated`` (D30, D32).

External semantic validation — "is this plan_code in *this* catalog?"
— belongs to the model layer per design constitution rule 8.  The
checks here are the structural invariants without which a
``Catalog`` instance is malformed.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated

__all__ = [
    "Catalog",
    "FeatureDefinition",
    "PlanDefinition",
]


@dataclasses.dataclass(frozen=True)
class PlanDefinition(_Validated):
    """A subscription plan tier.

    Attributes:
        plan_code: Short stable identifier (e.g. ``"BASIC"``).
        display_name: Human-readable name.
        monthly_price: Recurring monthly price as a quantized Decimal.
    """

    plan_code: str
    display_name: str
    monthly_price: Decimal

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("plan_code", str),
        ("display_name", str),
        ("monthly_price", Decimal),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this plan."""
        return (
            (
                bool(self.plan_code.strip()),
                "plan_code",
                self.plan_code,
            ),
            (
                bool(self.display_name.strip()),
                "display_name",
                self.display_name,
            ),
        )


@dataclasses.dataclass(frozen=True)
class FeatureDefinition(_Validated):
    """An optional add-on feature attachable to one or more plans.

    Attributes:
        feature_code: Short stable identifier.
        display_name: Human-readable name.
        monthly_price: Recurring monthly price as a quantized Decimal.
        allowed_plan_codes: Tuple of plan codes this feature may attach
            to.  Must contain at least one code.  Cross-reference
            resolution against actual plans is enforced by ``Catalog``.
    """

    feature_code: str
    display_name: str
    monthly_price: Decimal
    allowed_plan_codes: tuple[str, ...]

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("feature_code", str),
        ("display_name", str),
        ("monthly_price", Decimal),
        ("allowed_plan_codes", tuple),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this feature."""
        checks: list[CheckTuple] = [
            (
                bool(self.feature_code.strip()),
                "feature_code",
                self.feature_code,
            ),
            (
                bool(self.display_name.strip()),
                "display_name",
                self.display_name,
            ),
            (
                len(self.allowed_plan_codes) >= 1,
                "allowed_plan_codes",
                self.allowed_plan_codes,
            ),
        ]
        for index, code in enumerate(self.allowed_plan_codes):
            checks.append(
                (
                    isinstance(code, str) and bool(code.strip()),
                    f"allowed_plan_codes[{index}]",
                    code,
                )
            )
        return tuple(checks)


@dataclasses.dataclass(frozen=True)
class Catalog(_Validated):
    """The closed set of plans and features for a scenario.

    Construction validates the internal invariants:

    - at least one plan is present
    - plan codes are unique
    - feature codes are unique
    - every ``allowed_plan_codes`` entry on every feature resolves to a
      plan in this catalog
    """

    plans: tuple[PlanDefinition, ...]
    features: tuple[FeatureDefinition, ...]

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("plans", tuple),
        ("features", tuple),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this catalog."""
        checks: list[CheckTuple] = [
            (len(self.plans) >= 1, "plans", self.plans),
        ]

        # Element-type checks.
        for index, plan in enumerate(self.plans):
            checks.append(
                (
                    isinstance(plan, PlanDefinition),
                    f"plans[{index}]",
                    plan,
                )
            )
        for index, feature in enumerate(self.features):
            checks.append(
                (
                    isinstance(feature, FeatureDefinition),
                    f"features[{index}]",
                    feature,
                )
            )

        # Code-level checks run over the valid-typed subset so that
        # bad elements do not suppress duplicate-code or cross-ref
        # violations among the well-typed elements.
        valid_plans = [
            p for p in self.plans if isinstance(p, PlanDefinition)
        ]
        valid_features = [
            f for f in self.features if isinstance(f, FeatureDefinition)
        ]

        plan_codes = [p.plan_code for p in valid_plans]
        plan_code_set = set(plan_codes)
        checks.append(
            (
                len(plan_codes) == len(plan_code_set),
                "plans",
                plan_codes,
            )
        )

        feature_codes = [f.feature_code for f in valid_features]
        checks.append(
            (
                len(feature_codes) == len(set(feature_codes)),
                "features",
                feature_codes,
            )
        )

        for feature in valid_features:
            for code in feature.allowed_plan_codes:
                checks.append(
                    (
                        code in plan_code_set,
                        f"features.{feature.feature_code}"
                        f".allowed_plan_codes",
                        code,
                    )
                )

        return tuple(checks)
