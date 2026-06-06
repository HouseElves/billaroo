"""Decimal money helpers.

All money arithmetic uses Decimal.  Float inputs are rejected to prevent
silent precision loss.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

__all__ = ["build_money"]

_CENTS = Decimal("0.01")


def build_money(value: int | str | Decimal) -> Decimal:
    """Build a Decimal money value from a safe input type.

    Accepts int, str, or Decimal.  Rejects float to prevent silent
    precision loss (design constitution rule 13).

    The result is quantized to two decimal places (cents).

    Raises:
        TypeError: If *value* is a float or other unsupported type.
        ValueError: If *value* cannot be converted to Decimal.
    """
    if isinstance(value, bool):
        raise TypeError(f"bool is not a valid money input: {value!r}")
    if isinstance(value, float):
        raise TypeError(
            f"float is not a valid money input (use str or Decimal): {value!r}"
        )
    if not isinstance(value, (int, str, Decimal)):
        raise TypeError(f"Unsupported money input type: {type(value).__name__}")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Cannot convert {value!r} to Decimal") from exc
    if not d.is_finite():
        raise ValueError(f"Money must be finite: {value!r}")
    return d.quantize(_CENTS, rounding=ROUND_HALF_UP)
