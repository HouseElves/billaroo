"""Catalog construction helpers.

The model layer takes raw inputs (ints, strings, Decimals) and produces
validated catalog contract instances.  Prices are routed through
``build_money`` so the contract layer only ever sees ``Decimal``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from synthetic_billing.contracts.catalog_contracts import (
    Catalog,
    FeatureDefinition,
    PlanDefinition,
)
from synthetic_billing.model.money_model import build_money

__all__ = ["build_plan", "build_feature", "build_catalog"]


def build_plan(
    plan_code: str,
    plan_name: str,
    monthly_price: int | str | Decimal,
) -> PlanDefinition:
    """Build a validated ``PlanDefinition``.

    ``monthly_price`` accepts the same safe input types as
    ``build_money``: ``int``, ``str``, or ``Decimal``.  Floats are
    rejected at the boundary.
    """
    return PlanDefinition(
        plan_code=plan_code,
        plan_name=plan_name,
        monthly_price=build_money(monthly_price),
    )


def build_feature(
    feature_code: str,
    feature_name: str,
    monthly_price: int | str | Decimal,
    allowed_plan_codes: Iterable[str],
) -> FeatureDefinition:
    """Build a validated ``FeatureDefinition``.

    ``allowed_plan_codes`` is materialized to a tuple; any iterable
    works.  Cross-reference validity against a specific catalog is
    enforced when the feature is placed into a ``Catalog``.
    """
    return FeatureDefinition(
        feature_code=feature_code,
        feature_name=feature_name,
        monthly_price=build_money(monthly_price),
        allowed_plan_codes=tuple(allowed_plan_codes),
    )


def build_catalog(
    plans: Iterable[PlanDefinition],
    features: Iterable[FeatureDefinition],
) -> Catalog:
    """Build a validated ``Catalog`` from iterables of definitions."""
    return Catalog(plans=tuple(plans), features=tuple(features))
