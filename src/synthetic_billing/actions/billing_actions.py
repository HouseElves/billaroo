"""Billing semantic intent and the generate-invoice chain (D45).

A semantic action in this module applies one already-decided
account-month billing request to a :class:`SimulationState` and returns
an :class:`ActionResult` carrying the resulting invoice and invoice
lines (D43).  The intent records the already-decided request, and the
chain executor runs the single billing action.  Orchestrating
account-month billing across the simulation run — deciding which
accounts to bill in which months — is left to a later slice (D45) and
is not performed here.

Billing has no state mutation and no separate lifecycle-event step, so
the chain holds exactly one action (D45).  All billing rules — account
lookup, the active-account requirement, chargeability, catalog pricing,
invoice and line construction, total calculation, and line ordering —
live in :func:`build_account_month_invoice` (D44).  This action layer
only translates that model result into the accepted ``ActionResult``
shape; it computes no pricing or chargeability of its own.

The action class is private — the public API is the action chain
returned by :func:`build_generate_invoice_action_chain`.
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
from synthetic_billing.actions.action_protocols import (
    ActionResult,
    SemanticAction,
)
from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.model.billing_model import build_account_month_invoice
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = [
    "GenerateInvoiceIntent",
    "build_generate_invoice_action_chain",
]


# ---------------------------------------------------------------------------
# Intent contract (D45)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class GenerateInvoiceIntent(_Validated):
    """A semantic intent to bill one account for one simulation month.

    The intent records an already-decided request to generate one
    account-month invoice.  It carries only what identifies that
    request; the billing-cycle day, catalog prices, invoice identity,
    invoice total, subscription ids, and invoice lines are all resolved
    from state, catalog, and the billing model when the action is
    applied (D44, D45).

    Attributes:
        simulation_month: Simulation month to bill (1-indexed).  Month
            1 is valid: billing may occur in the first month (D42),
            unlike a cancellation, which never occurs in month 1 (D38).
        account_id: Account the invoice is generated for.
    """

    simulation_month: int
    account_id: str

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("simulation_month", int, bool),
        ("account_id", str),
    )

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this intent."""
        return (
            (
                self.simulation_month >= 1,
                "simulation_month",
                self.simulation_month,
            ),
            (
                bool(self.account_id.strip()),
                "account_id",
                self.account_id,
            ),
        )


# ---------------------------------------------------------------------------
# Private billing action (D45)
# ---------------------------------------------------------------------------


# The billing action holds only the intent and the catalog captured at
# chain construction; its job is one call to ``apply``.  R0903
# (too-few-public-methods) is by design — additional methods would
# predeclare capability that no concrete action requires (rule 22, D38).
@dataclasses.dataclass(frozen=True)
class _GenerateInvoiceAction:  # pylint: disable=too-few-public-methods
    """Generate one account-month invoice, delegating to the billing model.

    Calls :func:`build_account_month_invoice` with the applied state,
    the captured catalog, and the intent's account and month, then
    translates the result into an :class:`ActionResult`.  It performs
    no pricing or chargeability of its own and does not change state.
    Exceptions raised by the billing model propagate unchanged.
    """

    intent: GenerateInvoiceIntent
    catalog: Catalog

    def apply(self, state: SimulationState) -> ActionResult:
        """Return an ActionResult carrying the generated invoice and lines.

        When the billing model returns ``(invoice, invoice_lines)`` the
        result carries that single invoice and its ordered lines; when
        it returns ``None`` the billing collections are empty.  In both
        cases the original state is returned and no lifecycle events are
        emitted.
        """
        billed = build_account_month_invoice(
            state,
            self.catalog,
            self.intent.account_id,
            self.intent.simulation_month,
        )
        if billed is None:
            return ActionResult.create_validated(state, (), (), ())
        invoice, invoice_lines = billed
        return ActionResult.create_validated(
            state, (), (invoice,), invoice_lines,
        )


# ---------------------------------------------------------------------------
# Public chain builder (D45)
# ---------------------------------------------------------------------------


def build_generate_invoice_action_chain(
    intent: GenerateInvoiceIntent,
    catalog: Catalog,
) -> tuple[SemanticAction, ...]:
    """Build the one-action generate-invoice chain (D45).

    The returned tuple holds exactly one billing action: billing has no
    state mutation and no separate lifecycle-event step that would
    justify multiple actions.  The *catalog* is captured here and used
    by the action when applied.  ``intent`` itself is not inspected —
    the action and the billing model handle validation when applied.
    """
    return (_GenerateInvoiceAction(intent, catalog),)
