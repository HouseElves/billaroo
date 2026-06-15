"""Tests for synthetic_billing.actions.billing_actions."""

import dataclasses
from decimal import Decimal

import pytest

from synthetic_billing.actions.action_chain import apply_action_chain
from synthetic_billing.actions.action_protocols import ActionResult
from synthetic_billing.actions.billing_actions import (
    GenerateInvoiceIntent,
    build_generate_invoice_action_chain,
)
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.account_model import build_account
from synthetic_billing.model.billing_model import build_account_month_invoice
from synthetic_billing.model.catalog_model import (
    build_catalog,
    build_default_catalog,
    build_plan,
)
from synthetic_billing.model.subscriber_model import build_subscriber
from synthetic_billing.model.subscription_model import (
    build_feature_subscription,
    build_plan_subscription,
)
from synthetic_billing.simulate.simulation_state import SimulationState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CATALOG = build_default_catalog()


def _state_from(account, subscriptions_by_plan):
    """Build a validated state for one account from (plan_code, subs) specs.

    *subscriptions_by_plan* is a sequence of ``(plan_code, sub_specs)``
    pairs, one per subscriber on the account; each ``sub_specs`` is a
    sequence of subscription factories taking the derived subscriber id.
    Returning whole states (rather than exposing per-record builders)
    keeps the action tests focused on action behaviour, not record
    plumbing.
    """
    subscribers = []
    subscriptions = []
    for ordinal, (plan_code, sub_specs) in enumerate(subscriptions_by_plan):
        subscriber = build_subscriber(
            account.account_id, ordinal, plan_code, _CATALOG,
        )
        subscribers.append(subscriber)
        for make_sub in sub_specs:
            subscriptions.append(make_sub(subscriber.subscriber_id))
    return SimulationState.create_validated(
        (account,), tuple(subscribers), tuple(subscriptions),
    )


def _plan(plan_code, start_month=1, end_month=None,
          status=ACTIVE_SUBSCRIPTION_STATUS):
    """Return a factory building a plan subscription for a subscriber id."""
    def _make(subscriber_id):
        return build_plan_subscription(
            subscriber_id, plan_code, start_month, _CATALOG,
            end_month, status,
        )
    return _make


def _feature(feature_code, plan_code, start_month=1):
    """Return a factory building a feature subscription for a subscriber id."""
    def _make(subscriber_id):
        return build_feature_subscription(
            subscriber_id, feature_code, plan_code, start_month, _CATALOG,
        )
    return _make


def _account_with_status(status, ordinal=0, cycle_day=15):
    """Build an account with the given status and a derived id."""
    return build_account(
        f"acct-seed-{ordinal}", ordinal, cycle_day, "US-WEST", status,
    )


def _active_account(ordinal=0, cycle_day=15):
    """Build an active account with a derived id."""
    return _account_with_status("active", ordinal, cycle_day)


def _billable_state(cycle_day: int = 15):
    """Build a one-subscriber active-account state with a plan and feature.

    Returns the account and the state so tests can reference the
    derived account id.
    """
    account = _active_account(cycle_day=cycle_day)
    state = _state_from(
        account,
        [("STANDARD", (_plan("STANDARD"), _feature("CLOUD_DVR", "STANDARD")))],
    )
    return account, state


# ===========================================================================
# GenerateInvoiceIntent (D45)
# ===========================================================================


class TestGenerateInvoiceIntentHappyPath:
    """Valid GenerateInvoiceIntent construction and protocol."""

    def test_valid_intent(self) -> None:
        """A valid intent stores its fields."""
        intent = GenerateInvoiceIntent.create_validated(3, "acct-001")
        assert intent.simulation_month == 3
        assert intent.account_id == "acct-001"

    def test_month_one_is_accepted(self) -> None:
        """Month 1 is valid for billing (unlike cancellation)."""
        intent = GenerateInvoiceIntent.create_validated(1, "acct-001")
        assert intent.simulation_month == 1

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        intent = GenerateInvoiceIntent.create_validated(1, "acct-001")
        with pytest.raises(dataclasses.FrozenInstanceError):
            intent.account_id = "other"  # type: ignore[misc]

    def test_is_valid_true(self) -> None:
        """is_valid() is True for a structurally valid intent."""
        intent = GenerateInvoiceIntent.create_validated(1, "acct-001")
        assert intent.is_valid() is True


class TestGenerateInvoiceIntentTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_bool_simulation_month(self) -> None:
        """A bool month is rejected despite bool being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            GenerateInvoiceIntent.create_validated(True, "acct-001")
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_non_int_simulation_month(self) -> None:
        """A non-int month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            GenerateInvoiceIntent.create_validated("3", "acct-001")
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_non_string_account_id(self) -> None:
        """A non-string account id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            GenerateInvoiceIntent.create_validated(3, 42)
        assert any(
            f == "account_id" for f, _ in exc_info.value.violations
        )


class TestGenerateInvoiceIntentStructuralChecks:
    """Structural validation catches value errors."""

    def test_month_zero_rejected(self) -> None:
        """Month 0 is below the valid range."""
        with pytest.raises(InvalidRequestError) as exc_info:
            GenerateInvoiceIntent.create_validated(0, "acct-001")
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_negative_month_rejected(self) -> None:
        """A negative month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            GenerateInvoiceIntent.create_validated(-1, "acct-001")
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_blank_account_id_rejected(self) -> None:
        """A whitespace-only account id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            GenerateInvoiceIntent.create_validated(1, "   ")
        assert any(
            f == "account_id" for f, _ in exc_info.value.violations
        )


# ===========================================================================
# build_generate_invoice_action_chain — chain shape (D45)
# ===========================================================================


class TestGenerateInvoiceChainShape:
    """The chain builder returns a single-action tuple."""

    def test_returns_tuple(self) -> None:
        """The builder returns a tuple."""
        intent = GenerateInvoiceIntent.create_validated(1, "acct-001")
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        assert isinstance(chain, tuple)

    def test_exactly_one_action(self) -> None:
        """The chain contains exactly one semantic action."""
        intent = GenerateInvoiceIntent.create_validated(1, "acct-001")
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        assert len(chain) == 1

    def test_action_has_apply(self) -> None:
        """The single action exposes an apply method."""
        intent = GenerateInvoiceIntent.create_validated(1, "acct-001")
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        assert callable(chain[0].apply)

    def test_supplied_catalog_is_used(self) -> None:
        """The catalog passed to the builder is the one used to price.

        A catalog whose STANDARD plan is priced differently from the
        default must change the resulting invoice total, proving the
        builder's catalog (not some default) reaches the action.
        """
        acct = _active_account()
        state = _state_from(acct, [("STANDARD", (_plan("STANDARD"),))])
        # Build a catalog with a distinct STANDARD price.
        custom = build_catalog(
            [
                build_plan("STANDARD", "Standard Plan", "12.34"),
            ],
            [],
        )
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, custom)
        result = chain[0].apply(state)
        assert result.invoices[0].total_amount == Decimal("12.34")


# ===========================================================================
# Invoice-producing action behaviour (D45)
# ===========================================================================


class TestGenerateInvoiceActionProducesInvoice:
    """When billing is chargeable, the action returns one invoice."""

    def test_delegates_to_billing_model(self) -> None:
        """The action's invoice matches the D44 model output exactly."""
        acct, state = _billable_state()
        expected = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert expected is not None
        expected_invoice, expected_lines = expected
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert result.invoices == (expected_invoice,)
        assert result.invoice_lines == expected_lines

    def test_single_invoice_in_tuple(self) -> None:
        """A produced invoice appears as a one-element invoices tuple."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert len(result.invoices) == 1
        assert isinstance(result.invoices[0], Invoice)

    def test_lines_preserve_model_order(self) -> None:
        """Invoice lines preserve the D44 model ordering."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert all(
            isinstance(ln, InvoiceLine) for ln in result.invoice_lines
        )
        assert [ln.item_code for ln in result.invoice_lines] == [
            "STANDARD", "CLOUD_DVR",
        ]

    def test_no_lifecycle_events(self) -> None:
        """The billing action emits no lifecycle events."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert not result.lifecycle_events

    def test_state_returned_unchanged(self) -> None:
        """The original state object is returned unchanged."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert result.state is state

    def test_returns_validated_action_result(self) -> None:
        """The action returns a structurally valid ActionResult."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert isinstance(result, ActionResult)
        assert result.validate() is None

    def test_repeated_application_equal_records(self) -> None:
        """Equivalent inputs produce equal billing records."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        first = build_generate_invoice_action_chain(
            intent, _CATALOG,
        )[0].apply(state)
        second = build_generate_invoice_action_chain(
            intent, _CATALOG,
        )[0].apply(state)
        assert first.invoices == second.invoices
        assert first.invoice_lines == second.invoice_lines


# ===========================================================================
# End-to-end through apply_action_chain (D45)
# ===========================================================================


class TestGenerateInvoiceThroughChainExecutor:
    """The generated chain works with the unchanged apply_action_chain."""

    def test_state_identity_preserved(self) -> None:
        """The chain executor returns the original state object."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = apply_action_chain(state, chain)
        assert result.state is state

    def test_observable_result_matches_direct_apply(self) -> None:
        """Running through the executor matches applying the action directly."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        direct = chain[0].apply(state)
        via_chain = apply_action_chain(state, chain)
        assert via_chain.invoices == direct.invoices
        assert via_chain.invoice_lines == direct.invoice_lines
        assert not via_chain.lifecycle_events

    def test_at_most_one_invoice(self) -> None:
        """The chain yields zero or one invoice."""
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = apply_action_chain(state, chain)
        assert len(result.invoices) == 1


# ===========================================================================
# Empty billing action behaviour (D45)
# ===========================================================================


class TestGenerateInvoiceActionEmpty:
    """When nothing is chargeable, the action returns empty billing."""

    def test_no_chargeable_subscriptions(self) -> None:
        """An account whose subscriptions are all future returns empty."""
        acct = _active_account()
        state = _state_from(
            acct, [("BASIC", (_plan("BASIC", start_month=9),))],
        )
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert not result.invoices
        assert not result.invoice_lines

    def test_non_active_account(self) -> None:
        """A present non-active account returns empty billing."""
        acct = _account_with_status("suspended")
        state = _state_from(acct, [("BASIC", (_plan("BASIC"),))])
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert not result.invoices
        assert not result.invoice_lines

    def test_empty_state_unchanged(self) -> None:
        """State is unchanged when nothing is chargeable."""
        acct = _account_with_status("closed")
        state = SimulationState.create_validated((acct,), (), ())
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert result.state is state

    def test_empty_no_lifecycle_events(self) -> None:
        """No lifecycle events are emitted when nothing is chargeable."""
        acct = _account_with_status("closed")
        state = SimulationState.create_validated((acct,), (), ())
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert not result.lifecycle_events


# ===========================================================================
# Fail-loud behaviour: D44 exceptions propagate unchanged (D45)
# ===========================================================================


class TestGenerateInvoiceActionFailLoud:
    """Billing-model exceptions propagate through the action unchanged."""

    def test_missing_account_propagates(self) -> None:
        """A missing account surfaces the model's InvalidRequestError."""
        state = SimulationState.create_validated((), (), ())
        intent = GenerateInvoiceIntent.create_validated(1, "ghost")
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        assert any(
            f == "account_id" for f, _ in exc_info.value.violations
        )

    def test_unresolved_catalog_item_propagates(self) -> None:
        """An unpriceable chargeable subscription surfaces the model error."""
        acct = _active_account()
        good_state = _state_from(acct, [("BASIC", (_plan("BASIC"),))])
        good_plan = good_state.subscriptions[0]
        bad_plan = dataclasses.replace(good_plan, item_code="NONEXISTENT")
        state = SimulationState.create_validated(
            good_state.accounts, good_state.subscribers, (bad_plan,),
        )
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        with pytest.raises(InvalidRequestError) as exc_info:
            chain[0].apply(state)
        assert any(
            f == "item_code" for f, _ in exc_info.value.violations
        )

    def test_propagates_through_chain_executor(self) -> None:
        """The same failure propagates through apply_action_chain unchanged."""
        state = SimulationState.create_validated((), (), ())
        intent = GenerateInvoiceIntent.create_validated(1, "ghost")
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        with pytest.raises(InvalidRequestError):
            apply_action_chain(state, chain)


# ===========================================================================
# Scope protection / purity (D45)
# ===========================================================================


class TestGenerateInvoiceActionPurity:
    """The action is pure: no mutation, no randomness, no I/O."""

    def test_state_object_not_mutated(self) -> None:
        """The input state's tuples are unchanged after application."""
        acct, state = _billable_state()
        before = (state.accounts, state.subscribers, state.subscriptions)
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        chain[0].apply(state)
        assert (
            state.accounts, state.subscribers, state.subscriptions,
        ) == before

    def test_catalog_not_mutated(self) -> None:
        """The catalog is unchanged after application."""
        acct, state = _billable_state()
        before = (_CATALOG.plans, _CATALOG.features)
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        chain[0].apply(state)
        assert (_CATALOG.plans, _CATALOG.features) == before

    def test_no_random_stream_required(self) -> None:
        """Neither the builder nor the action takes a RandomStream.

        Billing is fully deterministic; no seeded randomness is
        threaded into the chain builder or the action's apply call.
        """
        acct, state = _billable_state()
        intent = GenerateInvoiceIntent.create_validated(1, acct.account_id)
        # Builder takes only (intent, catalog); apply takes only state.
        chain = build_generate_invoice_action_chain(intent, _CATALOG)
        result = chain[0].apply(state)
        assert isinstance(result, ActionResult)
