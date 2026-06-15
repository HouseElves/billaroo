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

from synthetic_billing._validation import CheckSpec, CheckTuple, _Validated
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

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this action result.

        Top-level field types are re-checked here so that
        direct-construction instances (which bypass
        :meth:`create_validated` and therefore the constructor type
        checks) are reported as invalid rather than silently passing.

        Per constitution rule 23, each output collection is checked
        independently: when one collection is not a tuple at all,
        only its per-element checks are skipped (iterating it would be
        unsafe), while the other, correctly-typed collections still
        surface their own per-element violations.
        """
        checks: list[CheckTuple] = [
            (
                isinstance(self.state, SimulationState),
                "state",
                self.state,
            ),
        ]
        checks.extend(
            self._collection_checks(
                "lifecycle_events", self.lifecycle_events, LifecycleEvent,
            )
        )
        checks.extend(
            self._collection_checks("invoices", self.invoices, Invoice)
        )
        checks.extend(
            self._collection_checks(
                "invoice_lines", self.invoice_lines, InvoiceLine,
            )
        )
        return tuple(checks)

    @staticmethod
    def _collection_checks(
        field_name: str,
        value: object,
        element_type: type,
    ) -> tuple[CheckTuple, ...]:
        """Return the top-level and per-element checks for one collection.

        The collection must be a tuple of *element_type* instances.
        When ``value`` is not a tuple, only the top-level check is
        returned: iterating a non-tuple is not a safely observable
        check (rule 23), so per-element checks are skipped for this
        collection without suppressing the others.
        """
        checks: list[CheckTuple] = [
            (isinstance(value, tuple), field_name, value),
        ]
        if isinstance(value, tuple):
            for index, element in enumerate(value):
                checks.append(
                    (
                        isinstance(element, element_type),
                        f"{field_name}[{index}]",
                        element,
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
