"""
Subscription construction helpers.

The model layer derives deterministic IDs, constructs validated
subscription contracts via ``Subscription.create_validated()``, and
performs semantic catalog validation (plan/feature membership and
feature-plan compatibility).

This is the first model builder to use the ``_Validated.create_validated``
construction path (D30, D31).
"""

from __future__ import annotations

from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
    Subscription,
)

__all__ = ["build_plan_subscription", "build_feature_subscription"]


# The subscriber context, plan code, month, catalog reference, and optional
# end/status parameters are the natural interface for this builder;
# collapsing them would obscure the API.
def build_plan_subscription(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    subscriber_id: str,
    plan_code: str,
    start_month: int,
    catalog: Catalog,
    end_month: int | None = None,
    subscription_status: str = ACTIVE_SUBSCRIPTION_STATUS,
) -> Subscription:
    """Build a validated plan :class:`Subscription` with a deterministic ID.

    Construction follows a four-step order (D15, D31):

    1. Derive ``subscription_id`` via ``derive_id``.
    2. Construct via ``Subscription.create_validated(...)`` which
       runs type checks and structural validation.
    3. Validate ``plan_code`` exists in *catalog*.
    4. Return the validated subscription.

    Args:
        subscriber_id: Parent subscriber identifier.
        plan_code: Plan code that must exist in *catalog*.
        start_month: Simulation month the subscription begins.
        catalog: The scenario's plan and feature catalog.
        end_month: Month the subscription ended, or ``None``.
        subscription_status: Defaults to ``"active"``.

    Returns:
        A frozen :class:`Subscription` instance.
    """
    subscription_id = derive_id(
        "subscription", subscriber_id, "plan", plan_code, start_month,
    )

    subscription = Subscription.create_validated(
        subscription_id,
        subscriber_id,
        PLAN_ITEM_TYPE,
        plan_code,
        start_month,
        end_month,
        subscription_status,
    )

    plan_codes = {p.plan_code for p in catalog.plans}
    if subscription.item_code not in plan_codes:
        raise ValueError(
            f"plan_code {subscription.item_code!r} not found in catalog; "
            f"valid codes: {sorted(plan_codes)}"
        )

    return subscription


# The extra plan_code parameter for feature-plan compatibility pushes
# the argument count above pylint's max-args=5.  The seven parameters
# are the natural interface for this builder; splitting them into a
# config object would add abstraction without clarity.
def build_feature_subscription(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    subscriber_id: str,
    feature_code: str,
    plan_code: str,
    start_month: int,
    catalog: Catalog,
    end_month: int | None = None,
    subscription_status: str = ACTIVE_SUBSCRIPTION_STATUS,
) -> Subscription:
    """Build a validated feature :class:`Subscription` with a deterministic ID.

    Construction follows a four-step order (D15, D31):

    1. Derive ``subscription_id`` via ``derive_id``.
    2. Construct via ``Subscription.create_validated(...)`` which
       runs type checks and structural validation.
    3. Validate ``feature_code`` exists in *catalog*, ``plan_code``
       exists in *catalog*, and the feature is compatible with the plan.
    4. Return the validated subscription.

    The *plan_code* parameter is required for feature-plan
    compatibility validation; it is not stored in the subscription.
    The subscription's ``item_code`` records the feature code.

    Args:
        subscriber_id: Parent subscriber identifier.
        feature_code: Feature code that must exist in *catalog*.
        plan_code: Plan the feature attaches to; must be in the
            feature's ``allowed_plan_codes``.
        start_month: Simulation month the subscription begins.
        catalog: The scenario's plan and feature catalog.
        end_month: Month the subscription ended, or ``None``.
        subscription_status: Defaults to ``"active"``.

    Returns:
        A frozen :class:`Subscription` instance.
    """
    subscription_id = derive_id(
        "subscription", subscriber_id, "feature", feature_code, start_month,
    )

    subscription = Subscription.create_validated(
        subscription_id,
        subscriber_id,
        FEATURE_ITEM_TYPE,
        feature_code,
        start_month,
        end_month,
        subscription_status,
    )

    feature_codes = {f.feature_code for f in catalog.features}
    if subscription.item_code not in feature_codes:
        raise ValueError(
            f"feature_code {subscription.item_code!r} not found in catalog; "
            f"valid codes: {sorted(feature_codes)}"
        )

    plan_codes = {p.plan_code for p in catalog.plans}
    if plan_code not in plan_codes:
        raise ValueError(
            f"plan_code {plan_code!r} not found in catalog; "
            f"valid codes: {sorted(plan_codes)}"
        )

    feature_def = next(
        f for f in catalog.features
        if f.feature_code == subscription.item_code
    )
    if plan_code not in feature_def.allowed_plan_codes:
        raise ValueError(
            f"feature {subscription.item_code!r} is not compatible with "
            f"plan code {plan_code!r}; allowed plans: "
            f"{sorted(feature_def.allowed_plan_codes)}"
        )

    return subscription
