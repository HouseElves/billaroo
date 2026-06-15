"""Invoice header and invoice-line record schemas.

Pure contract module: no I/O, no logging, no database, no pandas, no
model-layer imports, no randomness.

An :class:`Invoice` is the header for one account's bill in one
simulation month.  An :class:`InvoiceLine` is one recurring charge for
one subscription on that invoice.  These are the smallest record
shapes needed to represent a single account-month recurring bill
(D42).

This module defines only the record vocabulary and its structural
invariants.  Whether a subscription is chargeable, what an account's
total should be, how a total relates to its lines, and whether the
referenced account, subscriber, or subscription exists are collection
or semantic concerns owned by later billing slices, not by this
contract module (design constitution rule 8, D42).

Monetary fields are quantized-to-cents ``Decimal`` values.  The
contract layer checks the *shape* of an already-built amount (finite,
cents-quantized, non-negative); conversion of raw input into a money
``Decimal`` happens at the ``build_money`` boundary in the model layer
(D42).
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
from synthetic_billing.contracts.subscription_contracts import (
    SUBSCRIPTION_ITEM_TYPES,
)

__all__ = [
    "Invoice",
    "InvoiceLine",
]


_CENTS = Decimal("0.01")
"""Cent precision used for the quantization shape check.

This mirrors the cent precision the model-layer ``build_money``
boundary quantizes to.  It is duplicated here as a literal rather than
imported because a pure contract module must not import the model
layer; the value is a fixed property of the money representation, not
a shared mutable configuration.
"""


def _is_cents_quantized(amount: Decimal) -> bool:
    """Return whether *amount* is a finite Decimal quantized to cents.

    A finite Decimal is cents-quantized when its exponent is no finer
    than ``-2``.  Non-finite Decimals (``NaN``, ``Infinity``) are not
    cents-quantized.
    """
    if not amount.is_finite():
        return False
    return -amount.as_tuple().exponent <= 2


def _non_blank(field_name: str, value: str) -> CheckTuple:
    """Return a check tuple asserting *value* is a non-blank string.

    A small local helper shared by the two invoice records to express
    the repeated "identifier is a non-blank string" structural check
    once.  It deliberately stays inside this module rather than being
    promoted into shared validation vocabulary: it is a two-record
    convenience, not a cross-contract abstraction (constitution rule
    22).
    """
    return (bool(value.strip()), field_name, value)


def _non_negative_money(field_name: str, amount: Decimal) -> CheckTuple:
    """Return a check tuple asserting *amount* is finite and non-negative."""
    return (
        amount.is_finite() and amount >= Decimal("0"),
        field_name,
        amount,
    )


@dataclasses.dataclass(frozen=True)
class Invoice(_Validated):
    """An invoice header for one account in one simulation month.

    Declared grain (rule 15): one invoice header for one account in one
    simulation month.

    Billing may occur in simulation month 1, so the month lower bound
    is ``1`` (D42).  Unlike a lifecycle event, an invoice is not
    restricted to month 2 or later.

    This record does not validate that ``account_id`` exists in any
    particular :class:`SimulationState`; that is semantic validation
    for later billing behaviour (D42).

    Attributes:
        invoice_id: Deterministic identifier for this account-month
            invoice (D28, D42).
        simulation_month: Simulation month the invoice covers
            (1-indexed, at least ``1``).
        account_id: Owning account identifier.
        billing_cycle_day: Day of the month the cycle closes (1-28).
        total_amount: Invoice total as a finite, cents-quantized,
            non-negative ``Decimal``.
    """

    invoice_id: str
    simulation_month: int
    account_id: str
    billing_cycle_day: int
    total_amount: Decimal

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("invoice_id", str),
        ("simulation_month", int, bool),
        ("account_id", str),
        ("billing_cycle_day", int, bool),
        ("total_amount", Decimal),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this invoice."""
        return (
            _non_blank("invoice_id", self.invoice_id),
            (
                self.simulation_month >= 1,
                "simulation_month",
                self.simulation_month,
            ),
            _non_blank("account_id", self.account_id),
            (
                1 <= self.billing_cycle_day <= 28,
                "billing_cycle_day",
                self.billing_cycle_day,
            ),
            (
                _is_cents_quantized(self.total_amount),
                "total_amount",
                self.total_amount,
            ),
            _non_negative_money("total_amount", self.total_amount),
        )


@dataclasses.dataclass(frozen=True)
class InvoiceLine(_Validated):  # pylint: disable=too-many-instance-attributes
    """One recurring charge for one subscription on one invoice.

    Declared grain (rule 15): for the currently supported billing
    vocabulary, one recurring charge for one subscription on one
    invoice.

    The record is named :class:`InvoiceLine` rather than introducing a
    separate recurring-charge subtype; future taxes, fees, credits,
    adjustments, and usage lines are not predeclared here (D42).

    ``item_type`` reuses the existing subscription item-type vocabulary
    (:data:`SUBSCRIPTION_ITEM_TYPES`) so a recurring line names the
    same plan-or-feature kind the subscription carries.

    This record does not independently prove that the invoice,
    subscriber, or subscription exists, that the subscription belongs
    to the subscriber, that the item fields agree with the
    subscription, or that the line shares the invoice's account or
    month.  Those are collection or semantic invariants for later
    slices (D42).

    Attributes:
        invoice_line_id: Deterministic identifier for this line (D28,
            D42).
        invoice_id: The invoice this line belongs to.
        subscriber_id: The subscriber the charged subscription belongs
            to.
        subscription_id: The charged subscription.
        item_type: One of :data:`SUBSCRIPTION_ITEM_TYPES`.
        item_code: The plan or feature code charged.
        line_amount: Line charge as a finite, cents-quantized,
            non-negative ``Decimal``.
    """

    invoice_line_id: str
    invoice_id: str
    subscriber_id: str
    subscription_id: str
    item_type: str
    item_code: str
    line_amount: Decimal

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("invoice_line_id", str),
        ("invoice_id", str),
        ("subscriber_id", str),
        ("subscription_id", str),
        ("item_type", str),
        ("item_code", str),
        ("line_amount", Decimal),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this invoice line."""
        return (
            _non_blank("invoice_line_id", self.invoice_line_id),
            _non_blank("invoice_id", self.invoice_id),
            _non_blank("subscriber_id", self.subscriber_id),
            _non_blank("subscription_id", self.subscription_id),
            (
                self.item_type in SUBSCRIPTION_ITEM_TYPES,
                "item_type",
                self.item_type,
            ),
            _non_blank("item_code", self.item_code),
            (
                _is_cents_quantized(self.line_amount),
                "line_amount",
                self.line_amount,
            ),
            _non_negative_money("line_amount", self.line_amount),
        )
