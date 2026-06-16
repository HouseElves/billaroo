"""Semantic action protocol and ordered-chain result contract.

This module defines the minimum vocabulary the action layer needs (D38,
D43):

* :class:`SemanticAction` — the structural protocol every semantic
  action satisfies.  An action applies to a :class:`SimulationState`
  and produces an :class:`ActionResult`.  The protocol is intentionally
  not runtime-checkable; concrete actions are introduced (and matched)
  by import and call site, not by isinstance.
* :class:`ActionResult` — the frozen, validated record returned by an
  applied action or an applied action chain.  It carries the updated
  simulation state, the lifecycle events produced, and (since D43) the
  invoice headers and invoice lines produced.

No hidden-truth, payment, log, or generic record collections live here;
constitution rule 22 (and D38) requires those abstractions to earn
their existence under real implementation pressure.  Invoice and
invoice-line tuples earned their place when D42 supplied the billing
records they carry (D43); cancellation actions return them empty.
"""

from __future__ import annotations

import dataclasses
from typing import ClassVar, Protocol

from synthetic_billing._validation import (
    CheckSpec,
    CheckTuple,
    _Validated,
    collection_element_checks,
)
from synthetic_billing.contracts.event_contracts import LifecycleEvent
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = [
    "ActionResult",
    "SemanticAction",
]


@dataclasses.dataclass(frozen=True)
class ActionResult(_Validated):
    """The result of applying a semantic action or an action chain.

    Attributes:
        state: The updated simulation state after the action is applied.
        lifecycle_events: Lifecycle events the action produced, in
            emission order.  Empty when the action produced no events.
        invoices: Invoice headers the action produced, in emission
            order.  Empty when the action produced no invoices (D43).
        invoice_lines: Invoice lines the action produced, in emission
            order.  Empty when the action produced no lines (D43).

    This record carries billing output but does not reconcile it: it
    does not check that every line references an invoice in the same
    result, that invoice totals equal line totals, that identities are
    unique, or that records agree with the state.  Those are semantic
    or broader-boundary concerns deferred to later billing work (D43).
    """

    state: SimulationState
    lifecycle_events: tuple[LifecycleEvent, ...]
    invoices: tuple[Invoice, ...]
    invoice_lines: tuple[InvoiceLine, ...]

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = (
        ("state", SimulationState),
        ("lifecycle_events", tuple),
        ("invoices", tuple),
        ("invoice_lines", tuple),
    )

    # ActionResult (per-action) and SimulationResult (per-run) are
    # deliberately distinct types that happen to carry the same
    # state-plus-billing-collections shape (D40 keeps them separate even
    # when their fields coincide).  The per-element checking is shared
    # vocabulary (``collection_element_checks``); the field declarations
    # and this assembly are the irreducible residue of two intentionally
    # separate envelopes, so the duplicate-code report on this validated
    # shape is suppressed locally rather than collapsed into a shared
    # base class that D40 rejects.
    def _structural_checks(  # pylint: disable=duplicate-code
        self,
    ) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this action result.

        Re-checks ``state`` and validates each output collection with
        independent, rule-23-safe per-element checks so a
        directly-constructed (test-only) instance still reports its
        violations.
        """
        checks: list[CheckTuple] = [
            (isinstance(self.state, SimulationState), "state", self.state),
        ]
        checks.extend(
            collection_element_checks(
                "lifecycle_events", self.lifecycle_events, LifecycleEvent,
            )
        )
        checks.extend(
            collection_element_checks("invoices", self.invoices, Invoice)
        )
        checks.extend(
            collection_element_checks(
                "invoice_lines", self.invoice_lines, InvoiceLine,
            )
        )
        return tuple(checks)


# A semantic action is, by design, a single-method protocol: the
# whole point of the abstraction is that ``apply(state)`` is the only
# externally observable contract.  Additional methods would predeclare
# capability that no concrete action requires yet (constitution rule
# 22, D38).
class SemanticAction(Protocol):  # pylint: disable=too-few-public-methods
    """Structural protocol every semantic action satisfies.

    A semantic action applies one step of an already-selected business
    transition to a :class:`SimulationState` and returns an
    :class:`ActionResult` carrying the updated state and any lifecycle
    events produced by that step.  The action does not choose
    subscriber behaviour: the behaviour model chooses the transition,
    an intent records the chosen transition, and an ordered action
    chain applies its consequences one action at a time
    (``docs/action_chain_model.rst``).

    The protocol is intentionally not runtime-checkable: concrete
    actions are matched at import and call sites, not by isinstance
    (D38, constitution rule 22).
    """

    def apply(self, state: SimulationState) -> ActionResult:
        """Apply this action to ``state`` and return an ``ActionResult``."""
