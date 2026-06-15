"""Tests for synthetic_billing.contracts.invoice_contracts."""

import dataclasses
from decimal import Decimal

import pytest

from synthetic_billing._validation import _Validated
from synthetic_billing.contracts.invoice_contracts import Invoice, InvoiceLine
from synthetic_billing.contracts.subscription_contracts import (
    PLAN_ITEM_TYPE,
    SUBSCRIPTION_ITEM_TYPES,
)
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Invoice helpers
# ---------------------------------------------------------------------------


_VALID_INVOICE = {
    "invoice_id": "inv0001",
    "simulation_month": 1,
    "account_id": "acct0001",
    "billing_cycle_day": 15,
    "total_amount": Decimal("19.99"),
}


def _make_invoice(**overrides) -> Invoice:
    """Build a valid Invoice via create_validated, applying *overrides*."""
    kw = {**_VALID_INVOICE, **overrides}
    return Invoice.create_validated(
        kw["invoice_id"],
        kw["simulation_month"],
        kw["account_id"],
        kw["billing_cycle_day"],
        kw["total_amount"],
    )


def _direct_invoice(**overrides) -> Invoice:
    """Directly construct an Invoice (test-only invalid-instance path)."""
    kw = {**_VALID_INVOICE, **overrides}
    return Invoice(
        invoice_id=kw["invoice_id"],
        simulation_month=kw["simulation_month"],
        account_id=kw["account_id"],
        billing_cycle_day=kw["billing_cycle_day"],
        total_amount=kw["total_amount"],
    )


# ---------------------------------------------------------------------------
# InvoiceLine helpers
# ---------------------------------------------------------------------------


_VALID_LINE = {
    "invoice_line_id": "line0001",
    "invoice_id": "inv0001",
    "subscriber_id": "sub0001",
    "subscription_id": "subscription0001",
    "item_type": PLAN_ITEM_TYPE,
    "item_code": "BASIC",
    "line_amount": Decimal("9.99"),
}


def _make_line(**overrides) -> InvoiceLine:
    """Build a valid InvoiceLine via create_validated, applying *overrides*."""
    kw = {**_VALID_LINE, **overrides}
    return InvoiceLine.create_validated(
        kw["invoice_line_id"],
        kw["invoice_id"],
        kw["subscriber_id"],
        kw["subscription_id"],
        kw["item_type"],
        kw["item_code"],
        kw["line_amount"],
    )


def _direct_line(**overrides) -> InvoiceLine:
    """Directly construct an InvoiceLine (test-only invalid-instance path)."""
    kw = {**_VALID_LINE, **overrides}
    return InvoiceLine(
        invoice_line_id=kw["invoice_line_id"],
        invoice_id=kw["invoice_id"],
        subscriber_id=kw["subscriber_id"],
        subscription_id=kw["subscription_id"],
        item_type=kw["item_type"],
        item_code=kw["item_code"],
        line_amount=kw["line_amount"],
    )


# ---------------------------------------------------------------------------
# Invoice happy path & protocol
# ---------------------------------------------------------------------------


class TestInvoiceHappyPath:
    """Invoice stores validated fields in a frozen dataclass."""

    def test_is_validated_subclass(self) -> None:
        """Invoice inherits from _Validated."""
        assert issubclass(Invoice, _Validated)

    def test_constructs_with_defaults(self) -> None:
        """All fields are stored unchanged."""
        inv = _make_invoice()
        assert inv.invoice_id == "inv0001"
        assert inv.simulation_month == 1
        assert inv.account_id == "acct0001"
        assert inv.billing_cycle_day == 15
        assert inv.total_amount == Decimal("19.99")

    def test_month_one_is_valid(self) -> None:
        """Billing may occur in simulation month 1 (unlike lifecycle events)."""
        assert _make_invoice(simulation_month=1).simulation_month == 1

    def test_zero_total_is_valid(self) -> None:
        """A non-negative zero total is accepted."""
        assert _make_invoice(total_amount=Decimal("0.00")).total_amount == (
            Decimal("0.00")
        )

    def test_billing_cycle_day_bounds(self) -> None:
        """Days 1 and 28 are the inclusive valid bounds."""
        assert _make_invoice(billing_cycle_day=1).billing_cycle_day == 1
        assert _make_invoice(billing_cycle_day=28).billing_cycle_day == 28

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        inv = _make_invoice()
        with pytest.raises(dataclasses.FrozenInstanceError):
            inv.total_amount = Decimal("1.00")  # type: ignore[misc]

    def test_is_valid_true(self) -> None:
        """is_valid() is True for a structurally valid invoice."""
        assert _make_invoice().is_valid() is True


# ---------------------------------------------------------------------------
# Invoice type-check rejections (production construction path)
# ---------------------------------------------------------------------------


class TestInvoiceTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_non_string_invoice_id(self) -> None:
        """An integer invoice_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(invoice_id=42)
        assert ("invoice_id", 42) in exc_info.value.violations

    def test_bool_simulation_month(self) -> None:
        """Bool simulation_month is rejected despite being an int subclass."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(simulation_month=True)
        assert ("simulation_month", True) in exc_info.value.violations

    def test_float_simulation_month(self) -> None:
        """Float simulation_month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(simulation_month=1.0)
        assert ("simulation_month", 1.0) in exc_info.value.violations

    def test_non_string_account_id(self) -> None:
        """An integer account_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(account_id=42)
        assert ("account_id", 42) in exc_info.value.violations

    def test_bool_billing_cycle_day(self) -> None:
        """Bool billing_cycle_day is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(billing_cycle_day=True)
        assert ("billing_cycle_day", True) in exc_info.value.violations

    def test_float_billing_cycle_day(self) -> None:
        """Float billing_cycle_day is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(billing_cycle_day=15.0)
        assert ("billing_cycle_day", 15.0) in exc_info.value.violations

    def test_non_decimal_total(self) -> None:
        """A float total_amount is rejected (Decimal required)."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(total_amount=19.99)
        assert any(
            f == "total_amount" for f, _ in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# Invoice structural-check rejections
# ---------------------------------------------------------------------------


class TestInvoiceStructuralChecks:
    """Structural validation catches value and range errors."""

    def test_blank_invoice_id(self) -> None:
        """A whitespace-only invoice_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(invoice_id="   ")
        assert any(f == "invoice_id" for f, _ in exc_info.value.violations)

    def test_blank_account_id(self) -> None:
        """A whitespace-only account_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(account_id="")
        assert any(f == "account_id" for f, _ in exc_info.value.violations)

    def test_month_zero(self) -> None:
        """Month 0 is below the valid range."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(simulation_month=0)
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_negative_month(self) -> None:
        """A negative month is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(simulation_month=-1)
        assert any(
            f == "simulation_month" for f, _ in exc_info.value.violations
        )

    def test_billing_cycle_day_zero(self) -> None:
        """Day 0 is below the valid range."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(billing_cycle_day=0)
        assert any(
            f == "billing_cycle_day" for f, _ in exc_info.value.violations
        )

    def test_billing_cycle_day_29(self) -> None:
        """Day 29 is above the valid range."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(billing_cycle_day=29)
        assert any(
            f == "billing_cycle_day" for f, _ in exc_info.value.violations
        )

    def test_non_finite_total_nan(self) -> None:
        """A NaN total is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(total_amount=Decimal("NaN"))
        assert any(
            f == "total_amount" for f, _ in exc_info.value.violations
        )

    def test_non_finite_total_infinity(self) -> None:
        """An infinite total is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(total_amount=Decimal("Infinity"))
        assert any(
            f == "total_amount" for f, _ in exc_info.value.violations
        )

    def test_non_cent_quantized_total(self) -> None:
        """A sub-cent total is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(total_amount=Decimal("1.234"))
        assert any(
            f == "total_amount" for f, _ in exc_info.value.violations
        )

    def test_negative_total(self) -> None:
        """A negative total is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_invoice(total_amount=Decimal("-1.00"))
        assert any(
            f == "total_amount" for f, _ in exc_info.value.violations
        )

    def test_coarser_than_cents_is_valid(self) -> None:
        """A whole-dollar total quantizes coarser than cents and is valid."""
        assert _make_invoice(total_amount=Decimal("5")).is_valid() is True

    def test_collects_independent_violations(self) -> None:
        """Independent structural failures are collected together."""
        invalid = _direct_invoice(
            invoice_id="",
            simulation_month=0,
            account_id="",
            billing_cycle_day=99,
            total_amount=Decimal("-1.234"),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            invalid.validate()
        field_names = {f for f, _ in exc_info.value.violations}
        assert "invoice_id" in field_names
        assert "simulation_month" in field_names
        assert "account_id" in field_names
        assert "billing_cycle_day" in field_names
        assert "total_amount" in field_names

    def test_direct_invalid_is_valid_false(self) -> None:
        """Direct construction of an invalid invoice yields is_valid()=False."""
        assert _direct_invoice(account_id="").is_valid() is False


# ---------------------------------------------------------------------------
# InvoiceLine happy path & protocol
# ---------------------------------------------------------------------------


class TestInvoiceLineHappyPath:
    """InvoiceLine stores validated fields in a frozen dataclass."""

    def test_is_validated_subclass(self) -> None:
        """InvoiceLine inherits from _Validated."""
        assert issubclass(InvoiceLine, _Validated)

    def test_constructs_with_defaults(self) -> None:
        """All fields are stored unchanged."""
        line = _make_line()
        assert line.invoice_line_id == "line0001"
        assert line.invoice_id == "inv0001"
        assert line.subscriber_id == "sub0001"
        assert line.subscription_id == "subscription0001"
        assert line.item_type == PLAN_ITEM_TYPE
        assert line.item_code == "BASIC"
        assert line.line_amount == Decimal("9.99")

    def test_all_item_types_accepted(self) -> None:
        """Every subscription item type is a valid line item_type."""
        for item_type in SUBSCRIPTION_ITEM_TYPES:
            assert _make_line(item_type=item_type).item_type == item_type

    def test_zero_amount_is_valid(self) -> None:
        """A non-negative zero line amount is accepted."""
        assert _make_line(line_amount=Decimal("0.00")).line_amount == (
            Decimal("0.00")
        )

    def test_is_frozen(self) -> None:
        """Mutation raises FrozenInstanceError."""
        line = _make_line()
        with pytest.raises(dataclasses.FrozenInstanceError):
            line.line_amount = Decimal("1.00")  # type: ignore[misc]

    def test_is_valid_true(self) -> None:
        """is_valid() is True for a structurally valid line."""
        assert _make_line().is_valid() is True


# ---------------------------------------------------------------------------
# InvoiceLine type-check rejections (production construction path)
# ---------------------------------------------------------------------------


class TestInvoiceLineTypeChecks:
    """create_validated rejects wrong constructor types."""

    def test_non_string_invoice_line_id(self) -> None:
        """An integer invoice_line_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(invoice_line_id=42)
        assert ("invoice_line_id", 42) in exc_info.value.violations

    def test_non_string_invoice_id(self) -> None:
        """An integer invoice_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(invoice_id=42)
        assert ("invoice_id", 42) in exc_info.value.violations

    def test_non_string_subscriber_id(self) -> None:
        """An integer subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(subscriber_id=42)
        assert ("subscriber_id", 42) in exc_info.value.violations

    def test_non_string_subscription_id(self) -> None:
        """An integer subscription_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(subscription_id=42)
        assert ("subscription_id", 42) in exc_info.value.violations

    def test_non_string_item_type(self) -> None:
        """An integer item_type is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(item_type=42)
        assert ("item_type", 42) in exc_info.value.violations

    def test_non_string_item_code(self) -> None:
        """An integer item_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(item_code=42)
        assert ("item_code", 42) in exc_info.value.violations

    def test_non_decimal_amount(self) -> None:
        """A float line_amount is rejected (Decimal required)."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(line_amount=9.99)
        assert any(
            f == "line_amount" for f, _ in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# InvoiceLine structural-check rejections
# ---------------------------------------------------------------------------


class TestInvoiceLineStructuralChecks:
    """Structural validation catches value and vocabulary errors."""

    def test_blank_invoice_line_id(self) -> None:
        """A whitespace-only invoice_line_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(invoice_line_id="  ")
        assert any(
            f == "invoice_line_id" for f, _ in exc_info.value.violations
        )

    def test_blank_invoice_id(self) -> None:
        """A blank invoice_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(invoice_id="")
        assert any(f == "invoice_id" for f, _ in exc_info.value.violations)

    def test_blank_subscriber_id(self) -> None:
        """A blank subscriber_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(subscriber_id="")
        assert any(
            f == "subscriber_id" for f, _ in exc_info.value.violations
        )

    def test_blank_subscription_id(self) -> None:
        """A blank subscription_id is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(subscription_id="")
        assert any(
            f == "subscription_id" for f, _ in exc_info.value.violations
        )

    def test_unsupported_item_type(self) -> None:
        """An item_type outside the subscription vocabulary is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(item_type="tax")
        assert any(f == "item_type" for f, _ in exc_info.value.violations)

    def test_blank_item_code(self) -> None:
        """A blank item_code is rejected."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(item_code="")
        assert any(f == "item_code" for f, _ in exc_info.value.violations)

    def test_non_finite_amount_nan(self) -> None:
        """A NaN line amount is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(line_amount=Decimal("NaN"))
        assert any(f == "line_amount" for f, _ in exc_info.value.violations)

    def test_non_finite_amount_infinity(self) -> None:
        """An infinite line amount is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(line_amount=Decimal("Infinity"))
        assert any(f == "line_amount" for f, _ in exc_info.value.violations)

    def test_non_cent_quantized_amount(self) -> None:
        """A sub-cent line amount is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(line_amount=Decimal("9.999"))
        assert any(f == "line_amount" for f, _ in exc_info.value.violations)

    def test_negative_amount(self) -> None:
        """A negative line amount is rejected structurally."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _make_line(line_amount=Decimal("-9.99"))
        assert any(f == "line_amount" for f, _ in exc_info.value.violations)

    def test_collects_independent_violations(self) -> None:
        """Independent structural failures are collected together."""
        invalid = _direct_line(
            invoice_line_id="",
            invoice_id="",
            subscriber_id="",
            subscription_id="",
            item_type="tax",
            item_code="",
            line_amount=Decimal("-1.234"),
        )
        with pytest.raises(InvalidRequestError) as exc_info:
            invalid.validate()
        field_names = {f for f, _ in exc_info.value.violations}
        assert "invoice_line_id" in field_names
        assert "invoice_id" in field_names
        assert "subscriber_id" in field_names
        assert "subscription_id" in field_names
        assert "item_type" in field_names
        assert "item_code" in field_names
        assert "line_amount" in field_names

    def test_direct_invalid_is_valid_false(self) -> None:
        """Direct construction of an invalid line yields is_valid()=False."""
        assert _direct_line(item_type="tax").is_valid() is False
