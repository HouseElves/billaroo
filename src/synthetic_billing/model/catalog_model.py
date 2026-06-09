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

__all__ = ["build_plan", "build_feature", "build_catalog", "build_default_catalog"]


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


def build_default_catalog() -> Catalog:
    """Build a small deterministic catalog for baseline scenarios.

    The catalog contains three plans (BASIC, STANDARD, PREMIUM) and
    two features (CLOUD_DVR compatible with STANDARD and PREMIUM,
    INTL_CALLING compatible with all three plans).  Prices are
    intentionally round-number Decimals suitable for readable test
    output and straightforward invoice arithmetic.

    This is a convenience helper for population building and tests.
    Production-grade catalogs would be loaded from configuration files.
    """
    basic = build_plan("BASIC", "Basic Plan", "29.99")
    standard = build_plan("STANDARD", "Standard Plan", "49.99")
    premium = build_plan("PREMIUM", "Premium Plan", "79.99")

    cloud_dvr = build_feature(
        "CLOUD_DVR",
        "Cloud DVR",
        "9.99",
        ("STANDARD", "PREMIUM"),
    )
    intl_calling = build_feature(
        "INTL_CALLING",
        "International Calling",
        "14.99",
        ("BASIC", "STANDARD", "PREMIUM"),
    )

    return build_catalog(
        [basic, standard, premium],
        [cloud_dvr, intl_calling],
    )
