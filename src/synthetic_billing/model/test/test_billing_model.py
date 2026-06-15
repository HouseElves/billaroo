"""Tests for synthetic_billing.model.billing_model."""

from decimal import Decimal

import pytest

from synthetic_billing.contracts.id_contracts import derive_id
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.contracts.subscription_contracts import (
    FEATURE_ITEM_TYPE,
    PLAN_ITEM_TYPE,
)
from synthetic_billing.exceptions import InvalidRequestError
from synthetic_billing.model.billing_model import (
    build_invoice,
    build_invoice_line,
)


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
