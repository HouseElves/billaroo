"""Tests for synthetic_billing.model.money_model."""

from decimal import Decimal

import pytest

from synthetic_billing.model.money_model import build_money


class TestBuildMoneyHappyPath:
    """build_money converts safe inputs to cents-quantized Decimal."""

    def test_from_int(self) -> None:
        """Integer input is quantized to two decimal places."""
        assert build_money(5) == Decimal("5.00")

    def test_from_str(self) -> None:
        """String input is parsed and quantized."""
        assert build_money("19.99") == Decimal("19.99")

    def test_from_decimal(self) -> None:
        """Decimal input passes through quantized."""
        assert build_money(Decimal("3.10")) == Decimal("3.10")

    def test_zero(self) -> None:
        """Zero is a valid money value."""
        assert build_money(0) == Decimal("0.00")

    def test_negative(self) -> None:
        """Negative values are valid (credits, adjustments)."""
        assert build_money("-5") == Decimal("-5.00")


class TestBuildMoneyRounding:
    """Quantization rounds to cents using ROUND_HALF_UP."""

    def test_rounds_down_below_half(self) -> None:
        """Third decimal < 5 rounds down."""
        assert build_money("1.234") == Decimal("1.23")

    def test_rounds_up_at_half(self) -> None:
        """Third decimal == 5 rounds up (banker's rounding not used)."""
        assert build_money("1.235") == Decimal("1.24")

    def test_rounds_up_above_half(self) -> None:
        """Third decimal > 5 rounds up, potentially carrying."""
        assert build_money("9.999") == Decimal("10.00")

    def test_rounds_down_well_below_half(self) -> None:
        """Third decimal == 1 rounds down."""
        assert build_money("9.991") == Decimal("9.99")


class TestBuildMoneyRejection:
    """build_money rejects unsafe or invalid inputs."""

    def test_rejects_float(self) -> None:
        """Float is rejected to prevent silent precision loss."""
        with pytest.raises(TypeError, match="float"):
            build_money(3.14)

    def test_rejects_bool(self) -> None:
        """Bool True is rejected despite being an int subclass."""
        with pytest.raises(TypeError, match="bool"):
            build_money(True)

    def test_rejects_bool_false(self) -> None:
        """Bool False is rejected despite being an int subclass."""
        with pytest.raises(TypeError, match="bool"):
            build_money(False)

    def test_rejects_none(self) -> None:
        """None is not a supported input type."""
        with pytest.raises(TypeError):
            build_money(None)  # type: ignore[arg-type]

    def test_rejects_nan_string(self) -> None:
        """NaN is not finite."""
        with pytest.raises(ValueError, match="finite"):
            build_money("NaN")

    def test_rejects_inf_string(self) -> None:
        """Infinity is not finite."""
        with pytest.raises(ValueError, match="finite"):
            build_money("Infinity")

    def test_rejects_negative_inf_string(self) -> None:
        """Negative infinity is not finite."""
        with pytest.raises(ValueError, match="finite"):
            build_money("-Infinity")

    def test_rejects_nonsense_string(self) -> None:
        """An unparseable string cannot convert to Decimal."""
        with pytest.raises(ValueError):
            build_money("abc")

    def test_rejects_empty_string(self) -> None:
        """An empty string cannot convert to Decimal."""
        with pytest.raises(ValueError):
            build_money("")
