"""Account construction helpers.

The model layer derives deterministic IDs and produces validated
account contract instances.
"""

from __future__ import annotations

from synthetic_billing.contracts.account_contracts import Account
from synthetic_billing.contracts.id_contracts import derive_id

__all__ = ["build_account"]


def build_account(
    seed: int,
    account_ordinal: int,
    billing_cycle_day: int,
    region_code: str,
    account_status: str = "active",
) -> Account:
    """Build a validated :class:`Account` with a deterministic ID.

    The account ID is derived as
    ``derive_id("account", seed, account_ordinal)`` per D28, making it
    stable across repeated runs with the same scenario seed.

    Args:
        seed: Scenario seed (scopes the ID to a scenario).
        account_ordinal: Zero-based generation index.
        billing_cycle_day: Invoice close day (1–28).
        region_code: Short region identifier.
        account_status: Lifecycle status; defaults to ``"active"``.

    Returns:
        A frozen :class:`Account` instance.
    """
    account_id = derive_id("account", seed, account_ordinal)
    return Account(
        account_id=account_id,
        account_ordinal=account_ordinal,
        billing_cycle_day=billing_cycle_day,
        region_code=region_code,
        account_status=account_status,
    )
