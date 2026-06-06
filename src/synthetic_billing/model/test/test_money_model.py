"""Tests for synthetic_billing.model.money_model."""

import pytest
from decimal import Decimal

from synthetic_billing.model.money_model import build_money


class TestBuildMoneyHappyPath:
    """build_money converts safe inputs to cents-quantized Decimal."""

    def test_from_int(self) -> None:
        assert build_money(5) == Decimal("5.00")

    def test_from_str(self) -> None:
        assert build_money("19.99") == Decimal("19.99")

    def test_from_decimal(self) -> None:
        assert build_money(Decimal("3.10")) == Decimal("3.10")

    def test_zero(self) -> None:
        assert build_money(0) == Decimal("0.00")

    def test_negative(self) -> None:
        assert build_money("-5") == Decimal("-5.00")


class TestBuildMoneyRounding:
    """Quantization rounds to cents using ROUND_HALF_UP."""

    def test_rounds_down_below_half(self) -> None:
        assert build_money("1.234") == Decimal("1.23")

    def test_rounds_up_at_half(self) -> None:
        assert build_money("1.235") == Decimal("1.24")

    def test_rounds_up_above_half(self) -> None:
        assert build_money("9.999") == Decimal("10.00")

    def test_rounds_down_well_below_half(self) -> None:
        assert build_money("9.991") == Decimal("9.99")


class TestBuildMoneyRejection:
    """build_money rejects unsafe or invalid inputs."""

    def test_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="float"):
            build_money(3.14)

    def test_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="bool"):
            build_money(True)

    def test_rejects_bool_false(self) -> None:
        with pytest.raises(TypeError, match="bool"):
            build_money(False)

    def test_rejects_none(self) -> None:
        with pytest.raises(TypeError):
            build_money(None)  # type: ignore[arg-type]

    def test_rejects_nan_string(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            build_money("NaN")

    def test_rejects_inf_string(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            build_money("Infinity")

    def test_rejects_negative_inf_string(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            build_money("-Infinity")

    def test_rejects_nonsense_string(self) -> None:
        with pytest.raises(ValueError):
            build_money("abc")

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError):
            build_money("")
