"""
Subscriber construction helpers.

The model layer derives deterministic IDs, validates the plan code
against a catalog, and produces validated subscriber contract
instances.
"""

# pylint: disable=duplicate-code
# Reason: account and subscriber contracts intentionally duplicate the tiny
# validation helpers for now. D29 records this as real pressure toward a future
# shared validation vocabulary, but extraction is premature until another
# contract module repeats the pattern.

from __future__ import annotations

from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.subscriber_contracts import Subscriber

__all__ = ["build_subscriber"]


def build_subscriber(
    account_id: str,
    subscriber_ordinal: int,
    plan_code: str,
    catalog: Catalog,
    active: bool = True,
) -> Subscriber:
    """Build a validated :class:`Subscriber` with a deterministic ID.

    Construction follows a four-step order so that structural and
    semantic validation surface at the right layers:

    1. Derive ``subscriber_id`` via ``derive_id`` (D28).
    2. Construct the :class:`Subscriber`, which runs structural
       validation in ``__post_init__``.
    3. Validate the constructed ``subscriber.plan_code`` against
       *catalog* — the semantic boundary described in design
       constitution rule 8.
    4. Return the validated subscriber.

    Args:
        account_id: Parent account identifier.
        subscriber_ordinal: Zero-based index within the parent account.
        plan_code: Plan code that must exist in *catalog*.
        catalog: The scenario's plan and feature catalog.
        active: Whether the subscriber is active; defaults to ``True``.

    Returns:
        A frozen :class:`Subscriber` instance.
    """
    subscriber_id = derive_id("subscriber", account_id, subscriber_ordinal)

    subscriber = Subscriber(
        subscriber_id=subscriber_id,
        account_id=account_id,
        subscriber_ordinal=subscriber_ordinal,
        plan_code=plan_code,
        active=active,
    )

    plan_codes = {p.plan_code for p in catalog.plans}
    if subscriber.plan_code not in plan_codes:
        raise ValueError(
            f"plan_code {subscriber.plan_code!r} not found in catalog; "
            f"valid codes: {sorted(plan_codes)}"
        )

    return subscriber
