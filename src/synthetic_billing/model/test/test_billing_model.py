"""Tests for synthetic_billing.model.billing_model."""

from decimal import Decimal

import dataclasses

import pytest

from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.contracts.subscription_contracts import (
    ACTIVE_SUBSCRIPTION_STATUS,
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.account_model import build_account
from synthetic_billing.model.billing_model import (
    build_account_month_invoice,
    build_invoice,
    build_invoice_line,
)
from synthetic_billing.model.catalog_model import build_default_catalog
from synthetic_billing.model.subscriber_model import build_subscriber
from synthetic_billing.model.subscription_model import (
    build_feature_subscription,
    build_plan_subscription,
)
from synthetic_billing.simulate.simulation_state import SimulationState


class TestBuildInvoice:
    """build_invoice derives an account-month ID and routes money safely."""

    def test_returns_invoice(self) -> None:
        """The returned object is an Invoice instance."""
        inv = build_invoice("acct0001", 3, 15, "19.99")
        assert isinstance(inv, Invoice)

    def test_deterministic_id(self) -> None:
        """The invoice ID is derive_id('invoice', account_id, month)."""
        inv = build_invoice("acct0001", 3, 15, "19.99")
        assert inv.invoice_id == derive_id("invoice", "acct0001", 3)

    def test_id_ignores_amount_and_cycle_day(self) -> None:
        """billing_cycle_day and total_amount are not identity fields."""
        first = build_invoice("acct0001", 3, 15, "19.99")
        second = build_invoice("acct0001", 3, 28, "5.00")
        assert first.invoice_id == second.invoice_id

    def test_stable_repeated_construction(self) -> None:
        """Repeating the same call yields the same identity."""
        first = build_invoice("acct0001", 3, 15, "19.99")
        second = build_invoice("acct0001", 3, 15, "19.99")
        assert first.invoice_id == second.invoice_id

    def test_month_one_is_valid(self) -> None:
        """Invoices may be built for simulation month 1."""
        inv = build_invoice("acct0001", 1, 15, "19.99")
        assert inv.simulation_month == 1

    def test_int_amount_quantized(self) -> None:
        """An int total is quantized to cents through build_money."""
        inv = build_invoice("acct0001", 3, 15, 10)
        assert inv.total_amount == Decimal("10.00")

    def test_str_amount_quantized(self) -> None:
        """A sub-cent string total is rounded through build_money."""
        inv = build_invoice("acct0001", 3, 15, "19.999")
        assert inv.total_amount == Decimal("20.00")

    def test_decimal_amount(self) -> None:
        """A Decimal total passes through build_money quantization."""
        inv = build_invoice("acct0001", 3, 15, Decimal("19.99"))
        assert inv.total_amount == Decimal("19.99")

    def test_rejects_float_amount(self) -> None:
        """Float rejection fires at the build_money boundary."""
        with pytest.raises(TypeError, match="float"):
            build_invoice("acct0001", 3, 15, 19.99)  # type: ignore[arg-type]

    def test_rejects_bool_amount(self) -> None:
        """Bool rejection fires at the build_money boundary."""
        with pytest.raises(TypeError, match="bool"):
            build_invoice("acct0001", 3, 15, True)  # type: ignore[arg-type]

    def test_rejects_nan_amount(self) -> None:
        """NaN is rejected at the build_money boundary."""
        with pytest.raises(ValueError, match="finite"):
            build_invoice("acct0001", 3, 15, "NaN")

    def test_rejects_infinity_amount(self) -> None:
        """Infinity is rejected at the build_money boundary."""
        with pytest.raises(ValueError, match="finite"):
            build_invoice("acct0001", 3, 15, "Infinity")

    def test_rejects_invalid_text_amount(self) -> None:
        """Unparseable text is rejected at the build_money boundary."""
        with pytest.raises(ValueError, match="Decimal"):
            build_invoice("acct0001", 3, 15, "abc")


class TestBuildInvoiceLine:
    """build_invoice_line derives an invoice-subscription ID and routes money."""

    def test_returns_invoice_line(self) -> None:
        """The returned object is an InvoiceLine instance."""
        line = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", "9.99",
        )
        assert isinstance(line, InvoiceLine)

    def test_deterministic_id(self) -> None:
        """The line ID is derive_id('invoice_line', invoice_id, sub_id)."""
        line = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", "9.99",
        )
        assert line.invoice_line_id == derive_id(
            "invoice_line", "inv0001", "subscription0001"
        )

    def test_id_ignores_non_identity_fields(self) -> None:
        """Subscriber, item, and amount are not folded into line identity."""
        first = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", "9.99",
        )
        second = build_invoice_line(
            "inv0001", "subZZZ", "subscription0001", FEATURE_ITEM_TYPE,
            "HD", "1.00",
        )
        assert first.invoice_line_id == second.invoice_line_id

    def test_stable_repeated_construction(self) -> None:
        """Repeating the same call yields the same identity."""
        first = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", "9.99",
        )
        second = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", "9.99",
        )
        assert first.invoice_line_id == second.invoice_line_id

    def test_int_amount_quantized(self) -> None:
        """An int line amount is quantized to cents through build_money."""
        line = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", 9,
        )
        assert line.line_amount == Decimal("9.00")

    def test_str_amount_quantized(self) -> None:
        """A sub-cent string line amount is rounded through build_money."""
        line = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", "9.999",
        )
        assert line.line_amount == Decimal("10.00")

    def test_decimal_amount(self) -> None:
        """A Decimal line amount passes through build_money quantization."""
        line = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
            "BASIC", Decimal("9.99"),
        )
        assert line.line_amount == Decimal("9.99")

    def test_feature_item_type_accepted(self) -> None:
        """A feature line carries the feature item type."""
        line = build_invoice_line(
            "inv0001", "sub0001", "subscription0001", FEATURE_ITEM_TYPE,
            "HD", "1.00",
        )
        assert line.item_type == FEATURE_ITEM_TYPE

    def test_rejects_float_amount(self) -> None:
        """Float rejection fires at the build_money boundary."""
        with pytest.raises(TypeError, match="float"):
            build_invoice_line(
                "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
                "BASIC", 9.99,  # type: ignore[arg-type]
            )

    def test_rejects_bool_amount(self) -> None:
        """Bool rejection fires at the build_money boundary."""
        with pytest.raises(TypeError, match="bool"):
            build_invoice_line(
                "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
                "BASIC", True,  # type: ignore[arg-type]
            )

    def test_rejects_nan_amount(self) -> None:
        """NaN is rejected at the build_money boundary."""
        with pytest.raises(ValueError, match="finite"):
            build_invoice_line(
                "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
                "BASIC", "NaN",
            )

    def test_rejects_infinity_amount(self) -> None:
        """Infinity is rejected at the build_money boundary."""
        with pytest.raises(ValueError, match="finite"):
            build_invoice_line(
                "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
                "BASIC", "Infinity",
            )

    def test_rejects_invalid_text_amount(self) -> None:
        """Unparseable text is rejected at the build_money boundary."""
        with pytest.raises(ValueError, match="Decimal"):
            build_invoice_line(
                "inv0001", "sub0001", "subscription0001", PLAN_ITEM_TYPE,
                "BASIC", "abc",
            )

    def test_rejects_unsupported_item_type(self) -> None:
        """An unsupported item_type is rejected by the InvoiceLine contract."""
        with pytest.raises(InvalidRequestError) as exc_info:
            build_invoice_line(
                "inv0001", "sub0001", "subscription0001", "tax",
                "BASIC", "9.99",
            )
        assert any(f == "item_type" for f, _ in exc_info.value.violations)


# ===========================================================================
# build_account_month_invoice (D44)
# ===========================================================================


_CATALOG = build_default_catalog()

# Catalog prices used in expected-total assertions below.
_BASIC_PRICE = Decimal("29.99")
_STANDARD_PRICE = Decimal("49.99")
_PREMIUM_PRICE = Decimal("79.99")
_CLOUD_DVR_PRICE = Decimal("9.99")
_INTL_PRICE = Decimal("14.99")


def _account(ordinal: int = 0, status: str = "active", cycle_day: int = 15):
    """Build a validated Account with a derived id."""
    return build_account(
        f"acct-seed-{ordinal}", ordinal, cycle_day, "US-WEST", status,
    )


def _subscriber(account_id: str, ordinal: int, plan_code: str = "STANDARD"):
    """Build a validated Subscriber on *account_id* with a derived id."""
    return build_subscriber(account_id, ordinal, plan_code, _CATALOG)


def _plan_sub(
    subscriber_id: str,
    plan_code: str = "STANDARD",
    start_month: int = 1,
    end_month: int | None = None,
    status: str = ACTIVE_SUBSCRIPTION_STATUS,
):
    """Build a validated plan subscription with a derived id."""
    return build_plan_subscription(
        subscriber_id, plan_code, start_month, _CATALOG, end_month, status,
    )


def _feature_sub(
    subscriber_id: str,
    feature_code: str = "CLOUD_DVR",
    plan_code: str = "STANDARD",
    start_month: int = 1,
):
    """Build a validated feature subscription with a derived id."""
    return build_feature_subscription(
        subscriber_id, feature_code, plan_code, start_month, _CATALOG,
    )


class TestBuildAccountMonthInvoiceBasic:
    """Basic recurring billing for one active account-month (D44)."""

    def test_single_plan_one_line(self) -> None:
        """One plan subscription yields one invoice and one line."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        plan = _plan_sub(sub.subscriber_id, "STANDARD")
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert isinstance(invoice, Invoice)
        assert len(lines) == 1
        assert lines[0].item_code == "STANDARD"
        assert lines[0].line_amount == _STANDARD_PRICE

    def test_plan_and_feature_ordered_lines(self) -> None:
        """Plan plus feature subscriptions produce lines in state order."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        plan = _plan_sub(sub.subscriber_id, "STANDARD")
        feat = _feature_sub(sub.subscriber_id, "CLOUD_DVR", "STANDARD")
        state = SimulationState.create_validated(
            (acct,), (sub,), (plan, feat),
        )
        _invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert [ln.item_code for ln in lines] == ["STANDARD", "CLOUD_DVR"]
        assert [ln.line_amount for ln in lines] == [
            _STANDARD_PRICE, _CLOUD_DVR_PRICE,
        ]

    def test_multiple_subscribers_same_invoice(self) -> None:
        """Multiple subscribers on one account bill into one invoice."""
        acct = _account()
        sub_a = _subscriber(acct.account_id, 0, "BASIC")
        sub_b = _subscriber(acct.account_id, 1, "PREMIUM")
        plan_a = _plan_sub(sub_a.subscriber_id, "BASIC")
        plan_b = _plan_sub(sub_b.subscriber_id, "PREMIUM")
        state = SimulationState.create_validated(
            (acct,), (sub_a, sub_b), (plan_a, plan_b),
        )
        invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert len(lines) == 2
        assert all(ln.invoice_id == invoice.invoice_id for ln in lines)
        assert invoice.total_amount == _BASIC_PRICE + _PREMIUM_PRICE

    def test_other_account_subscriptions_excluded(self) -> None:
        """Subscriptions on other accounts are not billed."""
        acct = _account(0)
        other = _account(1)
        sub = _subscriber(acct.account_id, 0, "BASIC")
        other_sub = _subscriber(other.account_id, 1, "PREMIUM")
        plan = _plan_sub(sub.subscriber_id, "BASIC")
        other_plan = _plan_sub(other_sub.subscriber_id, "PREMIUM")
        state = SimulationState.create_validated(
            (acct, other),
            (sub, other_sub),
            (plan, other_plan),
        )
        invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert len(lines) == 1
        assert lines[0].subscriber_id == sub.subscriber_id
        assert invoice.total_amount == _BASIC_PRICE

    def test_invoice_uses_account_billing_cycle_day(self) -> None:
        """The invoice billing_cycle_day comes from the account."""
        acct = _account(cycle_day=7)
        sub = _subscriber(acct.account_id, 0, "BASIC")
        plan = _plan_sub(sub.subscriber_id, "BASIC")
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        invoice, _lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert invoice.billing_cycle_day == 7

    def test_total_equals_exact_line_sum(self) -> None:
        """The invoice total is the exact Decimal sum of its line amounts."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "PREMIUM")
        plan = _plan_sub(sub.subscriber_id, "PREMIUM")
        dvr = _feature_sub(sub.subscriber_id, "CLOUD_DVR", "PREMIUM")
        intl = _feature_sub(sub.subscriber_id, "INTL_CALLING", "PREMIUM")
        state = SimulationState.create_validated(
            (acct,), (sub,), (plan, dvr, intl),
        )
        invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert invoice.total_amount == sum(
            (ln.line_amount for ln in lines), Decimal("0"),
        )
        assert invoice.total_amount == (
            _PREMIUM_PRICE + _CLOUD_DVR_PRICE + _INTL_PRICE
        )


class TestBuildAccountMonthInvoiceEffectiveDates:
    """Half-open [start_month, end_month) chargeability (D44)."""

    def _state_with_plan(self, **plan_kwargs):
        """Build a one-subscriber state whose plan carries *plan_kwargs*."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "BASIC")
        plan = _plan_sub(sub.subscriber_id, "BASIC", **plan_kwargs)
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        return acct, state

    def test_month_one_subscription_chargeable_in_month_one(self) -> None:
        """A month-1 subscription is chargeable in month 1."""
        acct, state = self._state_with_plan(start_month=1)
        result = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert result is not None

    def test_chargeable_in_start_month(self) -> None:
        """A subscription is chargeable in its start month."""
        acct, state = self._state_with_plan(start_month=3)
        result = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 3,
        )
        assert result is not None

    def test_not_chargeable_in_end_month(self) -> None:
        """A subscription ending in month m is not chargeable in month m."""
        acct, state = self._state_with_plan(
            start_month=1, end_month=4, status="ended",
        )
        result = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 4,
        )
        assert result is None

    def test_chargeable_month_before_end(self) -> None:
        """A subscription ending in month m is chargeable in month m-1."""
        acct, state = self._state_with_plan(
            start_month=1, end_month=4, status="ended",
        )
        result = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 3,
        )
        assert result is not None

    def test_future_subscription_excluded(self) -> None:
        """A subscription that starts later is not chargeable now."""
        acct, state = self._state_with_plan(start_month=5)
        result = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 2,
        )
        assert result is None

    def test_previously_ended_subscription_excluded(self) -> None:
        """An already-ended subscription is not chargeable after its end."""
        acct, state = self._state_with_plan(
            start_month=1, end_month=3, status="ended",
        )
        result = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 6,
        )
        assert result is None

    def test_open_subscription_remains_chargeable(self) -> None:
        """An open (end_month=None) subscription stays chargeable later."""
        acct, state = self._state_with_plan(start_month=1, end_month=None)
        result = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 99,
        )
        assert result is not None


class TestBuildAccountMonthInvoiceEmpty:
    """Cases that correctly produce no invoice (D44)."""

    def test_account_with_no_subscribers(self) -> None:
        """An existing account with no subscribers returns None."""
        acct = _account()
        state = SimulationState.create_validated((acct,), (), ())
        assert build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        ) is None

    def test_account_with_no_chargeable_subscriptions(self) -> None:
        """Subscribers but no chargeable subscriptions returns None."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "BASIC")
        future = _plan_sub(sub.subscriber_id, "BASIC", start_month=9)
        state = SimulationState.create_validated((acct,), (sub,), (future,))
        assert build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        ) is None

    def test_non_active_account_returns_none(self) -> None:
        """A present non-active account produces no invoice."""
        acct = _account(status="suspended")
        sub = _subscriber(acct.account_id, 0, "BASIC")
        plan = _plan_sub(sub.subscriber_id, "BASIC")
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        assert build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        ) is None

    def test_closed_account_returns_none(self) -> None:
        """A closed account produces no invoice."""
        acct = _account(status="closed")
        sub = _subscriber(acct.account_id, 0, "BASIC")
        plan = _plan_sub(sub.subscriber_id, "BASIC")
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        assert build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        ) is None


class TestBuildAccountMonthInvoiceOrderingAndIdentity:
    """Line ordering, determinism, and preserved identities (D44)."""

    def test_line_order_follows_state_subscriptions(self) -> None:
        """Line order follows the order of state.subscriptions."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "PREMIUM")
        intl = _feature_sub(sub.subscriber_id, "INTL_CALLING", "PREMIUM")
        plan = _plan_sub(sub.subscriber_id, "PREMIUM")
        dvr = _feature_sub(sub.subscriber_id, "CLOUD_DVR", "PREMIUM")
        # Deliberately not plan-first in the tuple.
        state = SimulationState.create_validated(
            (acct,), (sub,), (intl, plan, dvr),
        )
        _invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert [ln.item_code for ln in lines] == [
            "INTL_CALLING", "PREMIUM", "CLOUD_DVR",
        ]

    def test_repeated_calls_return_equal_records(self) -> None:
        """Equivalent inputs return equal records in the same order."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        plan = _plan_sub(sub.subscriber_id, "STANDARD")
        feat = _feature_sub(sub.subscriber_id, "CLOUD_DVR", "STANDARD")
        state = SimulationState.create_validated(
            (acct,), (sub,), (plan, feat),
        )
        first = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        second = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert first == second

    def test_every_line_references_invoice(self) -> None:
        """Every returned line carries the returned invoice's id."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        plan = _plan_sub(sub.subscriber_id, "STANDARD")
        feat = _feature_sub(sub.subscriber_id, "CLOUD_DVR", "STANDARD")
        state = SimulationState.create_validated(
            (acct,), (sub,), (plan, feat),
        )
        invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 1,
        )
        assert all(ln.invoice_id == invoice.invoice_id for ln in lines)

    def test_deterministic_identities_preserved(self) -> None:
        """Invoice and line ids match the accepted D42 derivations."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        plan = _plan_sub(sub.subscriber_id, "STANDARD")
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        invoice, lines = build_account_month_invoice(
            state, _CATALOG, acct.account_id, 3,
        )
        assert invoice.invoice_id == derive_id(
            "invoice", acct.account_id, 3,
        )
        assert lines[0].invoice_line_id == derive_id(
            "invoice_line", invoice.invoice_id, plan.subscription_id,
        )


class TestBuildAccountMonthInvoiceFailures:
    """Catalog and input failures fail loudly (D44)."""

    def test_missing_account(self) -> None:
        """A missing account fails loudly."""
        state = SimulationState.create_validated((), (), ())
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(state, _CATALOG, "ghost", 1)
        assert any(
            f == "account_id" for f, _ in exc_info.value.violations
        )

    def test_blank_account_id(self) -> None:
        """A blank account id is rejected before lookup."""
        state = SimulationState.create_validated((), (), ())
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(state, _CATALOG, "   ", 1)
        assert any(
            f == "account_id" for f, _ in exc_info.value.violations
        )

    def test_non_int_simulation_month(self) -> None:
        """A non-int simulation month is rejected."""
        acct = _account()
        state = SimulationState.create_validated((acct,), (), ())
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(
                state, _CATALOG, acct.account_id, "1",  # type: ignore[arg-type]
            )
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_bool_simulation_month(self) -> None:
        """A bool simulation month is rejected (not an int for billing)."""
        acct = _account()
        state = SimulationState.create_validated((acct,), (), ())
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(
                state, _CATALOG, acct.account_id, True,  # type: ignore[arg-type]
            )
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_zero_simulation_month(self) -> None:
        """Month 0 is below the valid range."""
        acct = _account()
        state = SimulationState.create_validated((acct,), (), ())
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(state, _CATALOG, acct.account_id, 0)
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_unresolved_plan_fails_loud(self) -> None:
        """A chargeable plan absent from the catalog fails loudly.

        The subscription is constructed directly (test-only) to model
        contradictory state/catalog input that the builders would
        otherwise prevent.
        """
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "BASIC")
        good_plan = _plan_sub(sub.subscriber_id, "BASIC")
        bad_plan = dataclasses.replace(good_plan, item_code="NONEXISTENT")
        state = SimulationState.create_validated(
            (acct,), (sub,), (bad_plan,),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(state, _CATALOG, acct.account_id, 1)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "item_code" in field_names

    def test_unresolved_feature_fails_loud(self) -> None:
        """A chargeable feature absent from the catalog fails loudly."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        good_feat = _feature_sub(sub.subscriber_id, "CLOUD_DVR", "STANDARD")
        bad_feat = dataclasses.replace(good_feat, item_code="NONEXISTENT")
        state = SimulationState.create_validated(
            (acct,), (sub,), (bad_feat,),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(state, _CATALOG, acct.account_id, 1)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "item_code" in field_names

    def test_unknown_item_type_fails_loud(self) -> None:
        """A subscription item_type in neither catalog family fails loudly.

        A subscription whose ``item_type`` is neither ``plan`` nor
        ``feature`` cannot be priced.  Such an instance is built
        directly (test-only) to exercise the defensive pricing path,
        since the model builders only ever produce the two known
        item types.
        """
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "BASIC")
        good_plan = _plan_sub(sub.subscriber_id, "BASIC")
        unknown = dataclasses.replace(good_plan, item_type="bundle")
        state = SimulationState.create_validated(
            (acct,), (sub,), (unknown,),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(state, _CATALOG, acct.account_id, 1)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "item_type" in field_names
        assert "item_code" in field_names

    def test_item_code_in_wrong_family_not_matched(self) -> None:
        """A feature code carried by a plan subscription does not resolve.

        ``CLOUD_DVR`` is a valid *feature* code, but a plan-typed
        subscription carrying it must not match a feature definition;
        the wrong-family lookup fails loudly rather than silently
        pricing it.
        """
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "BASIC")
        good_plan = _plan_sub(sub.subscriber_id, "BASIC")
        wrong_family = dataclasses.replace(good_plan, item_code="CLOUD_DVR")
        state = SimulationState.create_validated(
            (acct,), (sub,), (wrong_family,),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            build_account_month_invoice(state, _CATALOG, acct.account_id, 1)
        field_names = {f for f, _ in exc_info.value.violations}
        assert "item_code" in field_names
        assert "item_type" in field_names


class TestBuildAccountMonthInvoicePurity:
    """The operation is pure: no mutation, no randomness, no integration."""

    def test_state_unchanged(self) -> None:
        """The input state object is unchanged after billing."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        plan = _plan_sub(sub.subscriber_id, "STANDARD")
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        before = (state.accounts, state.subscribers, state.subscriptions)
        build_account_month_invoice(state, _CATALOG, acct.account_id, 1)
        assert (
            state.accounts, state.subscribers, state.subscriptions,
        ) == before

    def test_catalog_unchanged(self) -> None:
        """The input catalog object is unchanged after billing."""
        acct = _account()
        sub = _subscriber(acct.account_id, 0, "STANDARD")
        plan = _plan_sub(sub.subscriber_id, "STANDARD")
        state = SimulationState.create_validated((acct,), (sub,), (plan,))
        before = (_CATALOG.plans, _CATALOG.features)
        build_account_month_invoice(state, _CATALOG, acct.account_id, 1)
        assert (_CATALOG.plans, _CATALOG.features) == before
