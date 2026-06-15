"""Invoice and invoice-line construction helpers and account-month billing.

The model layer derives deterministic IDs, routes monetary input
through the ``build_money`` boundary, and produces validated invoice
contract instances via ``create_validated`` (D32, D41, D42).

:func:`build_invoice` and :func:`build_invoice_line` construct
individual records only.  :func:`build_account_month_invoice` is the
pure one-account-month recurring-billing operation (D44): given a
state, a catalog, an account, and a month, it selects the account's
chargeable subscriptions, prices each from the catalog, and returns one
reconciled invoice plus its ordered lines (or ``None`` when nothing is
chargeable).  It does not apply a semantic action, integrate billing
across the simulation horizon, mutate state, or consume randomness;
those remain later-slice concerns.
"""

from __future__ import annotations

from decimal import Decimal

from synthetic_billing.contracts.account_contracts import (
    ACCOUNT_STATUSES,
    Account,
)
from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.contracts.subscription_contracts import (
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
    Subscription,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.money_model import build_money
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = [
    "build_account_month_invoice",
    "build_invoice",
    "build_invoice_line",
]

# The billable account status is the first (good-standing) entry in the
# account-status vocabulary.  Referencing it by name keeps the billing
# rule tied to the contract's definition rather than a magic string.
_ACTIVE_ACCOUNT_STATUS = ACCOUNT_STATUSES[0]


def build_invoice(
    account_id: str,
    simulation_month: int,
    billing_cycle_day: int,
    total_amount: int | str | Decimal,
) -> Invoice:
    """Build a validated :class:`Invoice` with a deterministic ID (D42).

    ``total_amount`` accepts the same safe input types as
    ``build_money``: ``int``, ``str``, or ``Decimal``.  ``float``,
    ``bool``, non-finite, and otherwise unsupported money input are
    rejected at the ``build_money`` boundary (rule 13).

    The invoice ID identifies an account-month invoice::

        derive_id("invoice", account_id, simulation_month)

    ``billing_cycle_day`` and ``total_amount`` are deliberately not
    identity fields (D42).

    Args:
        account_id: Owning account identifier.
        simulation_month: Simulation month the invoice covers
            (1-indexed; month 1 is valid for invoices).
        billing_cycle_day: Day of the month the cycle closes (1-28).
        total_amount: Invoice total as a safe money input.

    Returns:
        A frozen, validated :class:`Invoice`.
    """
    amount = build_money(total_amount)
    invoice_id = derive_id("invoice", account_id, simulation_month)
    return Invoice.create_validated(
        invoice_id,
        simulation_month,
        account_id,
        billing_cycle_day,
        amount,
    )


def build_invoice_line(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    invoice_id: str,
    subscriber_id: str,
    subscription_id: str,
    item_type: str,
    item_code: str,
    line_amount: int | str | Decimal,
) -> InvoiceLine:
    """Build a validated :class:`InvoiceLine` with a deterministic ID (D42).

    ``line_amount`` accepts the same safe input types as
    ``build_money``: ``int``, ``str``, or ``Decimal``.  ``float``,
    ``bool``, non-finite, and otherwise unsupported money input are
    rejected at the ``build_money`` boundary (rule 13).

    The line ID identifies a recurring charge for one subscription on
    one invoice::

        derive_id("invoice_line", invoice_id, subscription_id)

    The current grain permits at most one recurring charge for a
    subscription on an invoice, so repeating the same call with the
    same invoice and subscription yields the same line identity.  No
    ordinal, line type, item code, amount, or subscriber id is folded
    into the identity in anticipation of future line families (D42).

    Args:
        invoice_id: The invoice this line belongs to.
        subscriber_id: The subscriber the charged subscription belongs
            to.
        subscription_id: The charged subscription.
        item_type: One of the existing subscription item types.
        item_code: The plan or feature code charged.
        line_amount: Line charge as a safe money input.

    Returns:
        A frozen, validated :class:`InvoiceLine`.
    """
    amount = build_money(line_amount)
    invoice_line_id = derive_id("invoice_line", invoice_id, subscription_id)
    return InvoiceLine.create_validated(
        invoice_line_id,
        invoice_id,
        subscriber_id,
        subscription_id,
        item_type,
        item_code,
        amount,
    )

# ---------------------------------------------------------------------------
# One-account-month recurring billing (D44)
# ---------------------------------------------------------------------------


def _validate_billing_request(
    account_id: str,
    simulation_month: int,
) -> None:
    """Fail loudly on a structurally invalid account-month billing request.

    ``account_id`` must be a non-blank string usable for deterministic
    identity derivation; ``simulation_month`` must be an integer (never
    ``bool``) of at least ``1``.  These mirror the ``Invoice`` field
    invariants (D42) so a request that could never yield a valid
    invoice is rejected before any lookup work.
    """
    if not isinstance(account_id, str) or not account_id.strip():
        raise InvalidRequestError(
            "account_id must be a non-blank string",
            violations=(("account_id", account_id),),
        )
    if isinstance(simulation_month, bool) or not isinstance(
        simulation_month, int
    ):
        raise InvalidRequestError(
            "simulation_month must be an int",
            violations=(("simulation_month", simulation_month),),
        )
    if simulation_month < 1:
        raise InvalidRequestError(
            "simulation_month must be at least 1",
            violations=(("simulation_month", simulation_month),),
        )


def _find_account_or_raise(
    state: SimulationState,
    account_id: str,
) -> Account:
    """Return the account with this id from state, raising if absent.

    Account-id uniqueness inside :class:`SimulationState` is enforced
    by state validation, so any present match is the unique one.
    """
    matches = [a for a in state.accounts if a.account_id == account_id]
    if not matches:
        raise InvalidRequestError(
            f"Account {account_id} not present in state",
            violations=(("account_id", account_id),),
        )
    return matches[0]


def _is_chargeable(
    subscription: Subscription,
    simulation_month: int,
) -> bool:
    """Return whether *subscription* is chargeable in *simulation_month*.

    Applies the half-open effective-date convention
    ``[start_month, end_month)`` (D39): a subscription is chargeable
    once its start month has arrived and until — but not including —
    its end month.  An open (``end_month is None``) subscription stays
    chargeable.
    """
    if subscription.start_month > simulation_month:
        return False
    return (
        subscription.end_month is None
        or simulation_month < subscription.end_month
    )


def _price_subscription(
    subscription: Subscription,
    catalog: Catalog,
) -> Decimal:
    """Return the catalog's current monthly price for *subscription*.

    A plan subscription is priced from the matching
    :class:`PlanDefinition`; a feature subscription from the matching
    :class:`FeatureDefinition`.  An item code that resolves under no
    catalog family — or only under the wrong family for the
    subscription's ``item_type`` — is contradictory state/catalog
    input and fails loudly (it is never silently skipped or priced at
    zero).
    """
    if subscription.item_type == PLAN_ITEM_TYPE:
        for plan in catalog.plans:
            if plan.plan_code == subscription.item_code:
                return plan.monthly_price
    elif subscription.item_type == FEATURE_ITEM_TYPE:
        for feature in catalog.features:
            if feature.feature_code == subscription.item_code:
                return feature.monthly_price
    raise InvalidRequestError(
        f"Item code {subscription.item_code!r} of type "
        f"{subscription.item_type!r} does not resolve in the catalog",
        violations=(
            ("item_type", subscription.item_type),
            ("item_code", subscription.item_code),
        ),
    )


def build_account_month_invoice(
    state: SimulationState,
    catalog: Catalog,
    account_id: str,
    simulation_month: int,
) -> tuple[Invoice, tuple[InvoiceLine, ...]] | None:
    """Build one account's recurring invoice for one simulation month (D44).

    Selects the chargeable subscriptions belonging to subscribers on
    *account_id*, prices each from *catalog*, builds one invoice line
    per chargeable subscription (in ``state.subscriptions`` order), and
    builds one invoice header whose total is the exact ``Decimal`` sum
    of those lines.

    Only an account whose status is active is billable.  A present
    non-active account, an account with no subscribers, and an account
    whose subscriptions are all non-chargeable in *simulation_month*
    each produce no invoice.

    Args:
        state: The simulation state to bill against (never mutated).
        catalog: The catalog supplying current monthly prices (never
            mutated).
        account_id: The account to bill.
        simulation_month: The month to bill (1-indexed).

    Returns:
        ``(invoice, invoice_lines)`` with a non-empty line tuple when at
        least one subscription is chargeable; ``None`` when the account
        exists but has nothing chargeable.

    Raises:
        InvalidRequestError: If the request is structurally invalid, the
            account is absent, or a chargeable subscription cannot be
            priced from the catalog.
    """
    _validate_billing_request(account_id, simulation_month)
    account = _find_account_or_raise(state, account_id)
    if account.account_status != _ACTIVE_ACCOUNT_STATUS:
        return None

    account_subscriber_ids = frozenset(
        sub.subscriber_id
        for sub in state.subscribers
        if sub.account_id == account_id
    )
    chargeable = tuple(
        subscription
        for subscription in state.subscriptions
        if subscription.subscriber_id in account_subscriber_ids
        and _is_chargeable(subscription, simulation_month)
    )
    if not chargeable:
        return None

    line_amounts = tuple(
        _price_subscription(subscription, catalog)
        for subscription in chargeable
    )
    total_amount = sum(line_amounts, Decimal("0"))
    invoice = build_invoice(
        account_id,
        simulation_month,
        account.billing_cycle_day,
        total_amount,
    )
    invoice_lines = tuple(
        build_invoice_line(
            invoice.invoice_id,
            subscription.subscriber_id,
            subscription.subscription_id,
            subscription.item_type,
            subscription.item_code,
            amount,
        )
        for subscription, amount in zip(chargeable, line_amounts)
    )
    return invoice, invoice_lines
