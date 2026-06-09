"""Catalog construction helpers.

The model layer takes raw inputs (ints, strings, Decimals) and produces
validated catalog contract instances via ``create_validated`` (D32).
Prices are routed through ``build_money`` so the contract layer only
ever sees ``Decimal``.
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
    display_name: str,
    monthly_price: int | str | Decimal,
) -> PlanDefinition:
    """Build a validated ``PlanDefinition``.

    ``monthly_price`` accepts the same safe input types as
    ``build_money``: ``int``, ``str``, or ``Decimal``.  Floats are
    rejected at the boundary.
    """
    return PlanDefinition.create_validated(
        plan_code,
        display_name,
        build_money(monthly_price),
    )


def build_feature(
    feature_code: str,
    display_name: str,
    monthly_price: int | str | Decimal,
    allowed_plan_codes: Iterable[str],
) -> FeatureDefinition:
    """Build a validated ``FeatureDefinition``.

    ``allowed_plan_codes`` is materialized to a tuple; any iterable
    works.  Cross-reference validity against a specific catalog is
    enforced when the feature is placed into a ``Catalog``.
    """
    return FeatureDefinition.create_validated(
        feature_code,
        display_name,
        build_money(monthly_price),
        tuple(allowed_plan_codes),
    )


def build_catalog(
    plans: Iterable[PlanDefinition],
    features: Iterable[FeatureDefinition],
) -> Catalog:
    """Build a validated ``Catalog`` from iterables of definitions."""
    return Catalog.create_validated(tuple(plans), tuple(features))
