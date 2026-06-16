"""Monthly simulation driver (D40, D46).

:func:`run_monthly_simulation` advances the starter-population state
through simulation months ``2 .. config.months``, selecting
cancellation intents at the start of each month and applying them in
stable order, then bills every month — including month 1 — against the
post-transition state.  The final :class:`SimulationResult` carries the
post-simulation state, the ordered event log, and the ordered invoices
and invoice lines.

Per-month ordering (D46): within a month, lifecycle transitions occur
first and billing observes the resulting effective-dated state, so a
subscription that ends in month ``m`` is not charged in month ``m``
(the half-open ``[start_month, end_month)`` convention from D39).
Month 1 has no post-starter transition but is still billed.

The driver does not draw randomness, apply chains, or compute pricing
itself.  It delegates:

* :func:`behavior_model.choose_cancellation_intents` selects intents
  from the month-start state, drawing exactly once per active
  subscriber;
* :func:`actions.lifecycle_actions.build_cancel_subscriber_action_chain`
  expands each intent into an ordered action chain;
* :func:`actions.billing_actions.build_generate_invoice_action_chain`
  expands one account-month billing request into a one-action chain
  delegating to :func:`model.billing_model.build_account_month_invoice`
  (D44, D45);
* :func:`actions.action_chain.apply_action_chain` applies each chain
  and returns the threaded state and accumulated records.

Billing consumes no randomness and emits no lifecycle events, so adding
it leaves the established cancellation draw sequence unchanged (D46):
month 1 billing happens before the month loop begins, and within each
later month billing runs only after that month's cancellation draws and
applications are complete.
"""

from __future__ import annotations

from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.actions.billing_actions import (
    GenerateInvoiceIntent,
    build_generate_invoice_action_chain,
)
from synthetic_billing.actions.lifecycle_actions import (
    build_cancel_subscriber_action_chain,
)
from synthetic_billing.contracts.catalog_contracts import Catalog
from synthetic_billing.contracts.event_contracts import LifecycleEvent
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.simulate.behavior_model import (
    choose_cancellation_intents,
    validate_cancellation_only_scope,
)
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import ScenarioConfig
from synthetic_billing.simulate.simulation_result import SimulationResult
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = ["run_monthly_simulation"]


def run_monthly_simulation(
    starter_state: SimulationState,
    config: ScenarioConfig,
    rng: RandomStream,
    catalog: Catalog,
) -> SimulationResult:
    """Run the monthly simulation over ``starter_state`` and return the result.

    Iterates ``simulation_month`` from ``1`` through ``config.months``
    inclusive.  Month 1 is the starter-population month: it performs no
    cancellation selection (those begin in month 2, D38/D40) but is
    billed.  For each month ``2 .. config.months``:

    1. Snapshot the current state as the month-start state.
    2. Choose cancellation intents from that snapshot (one draw per
       active subscriber in stable order).
    3. Apply each cancellation chain in selection order, threading
       state and accumulating lifecycle events.

    After any transitions for the month are applied, every account in
    the resulting state is billed for that month in stable account
    order; chargeable account-months contribute one invoice and its
    ordered lines (D44, D45).  Billing observes the post-transition
    state, so a subscription that ended this month is not charged this
    month.

    Configuration is checked up front: any non-cancellation monthly
    behaviour configured non-zero (or any configured coherency group)
    fails loudly before the loop begins.

    Args:
        starter_state: The validated post-construction starter
            population (treated as month 1 by convention).
        config: Scenario configuration; ``months`` and ``prob_cancel``
            drive the loop.
        rng: Caller-supplied seeded random stream.  Used only for
            cancellation selection; billing consumes no draws, so the
            stream position evolves exactly as in the cancellation-only
            driver.
        catalog: The catalog supplying current monthly prices for
            billing.

    Returns:
        A validated :class:`SimulationResult` carrying the final state,
        the ordered lifecycle events, and the ordered invoices and
        invoice lines.
    """
    validate_cancellation_only_scope(config)

    current_state: SimulationState = starter_state
    accumulated_events: tuple[LifecycleEvent, ...] = ()
    accumulated_invoices: tuple[Invoice, ...] = ()
    accumulated_lines: tuple[InvoiceLine, ...] = ()

    for simulation_month in range(1, config.months + 1):
        # Months >= 2 may carry cancellation transitions, selected from
        # the month-start state so intra-month mutations cannot
        # influence draws (D40).  Month 1 has no post-starter
        # transition and consumes no draws (D38).
        if simulation_month >= 2:
            current_state, month_events = _apply_month_cancellations(
                current_state, config, rng, simulation_month,
            )
            accumulated_events = accumulated_events + month_events

        # Billing observes the post-transition state for the month and
        # consumes no randomness (D46).
        month_invoices, month_lines = _bill_month(
            current_state, catalog, simulation_month,
        )
        accumulated_invoices = accumulated_invoices + month_invoices
        accumulated_lines = accumulated_lines + month_lines

    return SimulationResult.create_validated(
        current_state,
        accumulated_events,
        accumulated_invoices,
        accumulated_lines,
    )


def _apply_month_cancellations(
    month_start_state: SimulationState,
    config: ScenarioConfig,
    rng: RandomStream,
    simulation_month: int,
) -> tuple[SimulationState, tuple[LifecycleEvent, ...]]:
    """Select and apply this month's cancellations; return state and events.

    Intents are chosen once from *month_start_state* (D40), then each
    cancellation chain is applied in selection order, threading state.
    This is the only place the driver consumes randomness; billing adds
    none (D46).
    """
    intents = choose_cancellation_intents(
        month_start_state, config, rng, simulation_month,
    )
    current_state = month_start_state
    events: tuple[LifecycleEvent, ...] = ()
    for intent in intents:
        chain = build_cancel_subscriber_action_chain(intent)
        step = apply_action_chain(current_state, chain)
        current_state = step.state
        events = events + step.lifecycle_events
    return current_state, events


def _bill_month(
    state: SimulationState,
    catalog: Catalog,
    simulation_month: int,
) -> tuple[tuple[Invoice, ...], tuple[InvoiceLine, ...]]:
    """Bill every account in *state* for *simulation_month*.

    Walks ``state.accounts`` in stable order and, for each account,
    builds and applies the one-action generate-invoice chain (D45)
    against *state*.  A chargeable account-month contributes its single
    invoice and that invoice's ordered lines; a non-chargeable
    account-month contributes nothing.  Invoices are therefore ordered
    by account, and each invoice's lines keep the order
    :func:`build_account_month_invoice` produced (D44).

    Billing delegates entirely to the existing semantic-action and
    billing-model boundaries: this helper selects which account-months
    to bill, but the active-account rule, chargeability, catalog
    pricing, construction, and reconciliation all stay in the billing
    model (D44).  The state is never mutated and no randomness is
    consumed.
    """
    invoices: tuple[Invoice, ...] = ()
    lines: tuple[InvoiceLine, ...] = ()
    for account in state.accounts:
        intent = GenerateInvoiceIntent.create_validated(
            simulation_month, account.account_id,
        )
        chain = build_generate_invoice_action_chain(intent, catalog)
        step = apply_action_chain(state, chain)
        invoices = invoices + step.invoices
        lines = lines + step.invoice_lines
    return invoices, lines
