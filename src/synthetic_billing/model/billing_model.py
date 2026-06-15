"""Invoice and invoice-line construction helpers.

The model layer derives deterministic IDs, routes monetary input
through the ``build_money`` boundary, and produces validated invoice
contract instances via ``create_validated`` (D32, D41, D42).

These builders construct individual records only.  They do not decide
which subscriptions are chargeable, calculate an account's total from
its lines, look up catalog prices, or reconcile an invoice against its
lines; those are later billing-slice concerns (D42).
"""

from __future__ import annotations

from decimal import Decimal

from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.model.money_model import build_money

__all__ = ["build_invoice", "build_invoice_line"]


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
