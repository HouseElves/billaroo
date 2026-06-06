"""Scenario configuration for the synthetic billing simulator.

A ScenarioConfig is a frozen dataclass.  Validation is structural only:
shape, type, range, and syntax (design constitution rule 3).  No external
state is checked.

Coherency groups
----------------

Some optional fields only make sense as a set.  A "coherency group" is
a tuple of fields that must all be present together or all absent
together.  Mixed states are rejected with TypeError.

The v0 groups are:

    price_increase
        price_increase_month, price_increase_amount,
        price_increase_cancel_lift

        These three knobs configure a single price-increase scenario.
        A month with no amount is meaningless; an amount with no month
        is undated; a cancel lift with no price increase has nothing
        to react to.

    duplicate_invoice_line_defect
        duplicate_invoice_line_month, duplicate_invoice_line_probability

        These two knobs configure a single billing-defect scenario.
        A month with no probability is silent; a probability with no
        month is undated.

Design decision: we deliberately do *not* declare additional groups
beyond these two.  The required probabilities (prob_cancel,
prob_reactivate, prob_upgrade, prob_downgrade, etc.) are paired
conceptually but each is independently required and a coherency check
would add no information.  Speculative groupings violate the
"abstractions must earn their existence" rule (design constitution
rule 22).  New groups should be added here when a new optional scenario
knob set lands.
"""

from __future__ import annotations

import dataclasses
import pathlib
from decimal import Decimal
from typing import Optional

import yaml

from synthetic_billing.model.money_model import build_money

__all__ = ["ScenarioConfig", "load_scenario_config", "COHERENCY_GROUPS"]


# Coherency groups: each entry is (group_name, field_names_tuple).
# Within a group, all fields must be None or all must be non-None.
COHERENCY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "price_increase",
        (
            "price_increase_month",
            "price_increase_amount",
            "price_increase_cancel_lift",
        ),
    ),
    (
        "duplicate_invoice_line_defect",
        (
            "duplicate_invoice_line_month",
            "duplicate_invoice_line_probability",
        ),
    ),
)


def _validate_probability(name: str, value: object) -> float:
    """Check that *value* is a real number in [0, 1]."""
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a number, not bool")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be between 0 and 1, got {value}")
    return float(value)


@dataclasses.dataclass(frozen=True)
class ScenarioConfig:
    """Immutable scenario configuration.

    All probabilities are plain floats in [0, 1].
    Money fields are Decimal (quantized to cents).
    """

    seed: int
    months: int
    starting_accounts: int

    # -- behaviour probabilities --
    prob_cancel: float
    prob_upgrade: float
    prob_downgrade: float
    prob_feature_add: float
    prob_feature_remove: float
    prob_reactivate: float
    prob_payment_failure: float

    # -- optional price-increase scenario knobs (coherency group) --
    price_increase_month: Optional[int] = None
    price_increase_amount: Optional[Decimal] = None
    price_increase_cancel_lift: Optional[float] = None

    # -- optional billing-defect knobs (coherency group) --
    duplicate_invoice_line_month: Optional[int] = None
    duplicate_invoice_line_probability: Optional[float] = None

    def __post_init__(self) -> None:
        # --- seed ---
        if isinstance(self.seed, bool):
            raise TypeError("seed must be int, not bool")
        if not isinstance(self.seed, int):
            raise TypeError(f"seed must be int, got {type(self.seed).__name__}")

        # --- months ---
        if not isinstance(self.months, int) or isinstance(self.months, bool):
            raise TypeError(f"months must be int, got {type(self.months).__name__}")
        if self.months <= 0:
            raise ValueError(f"months must be > 0, got {self.months}")

        # --- starting_accounts ---
        if not isinstance(self.starting_accounts, int) or isinstance(
            self.starting_accounts, bool
        ):
            raise TypeError(
                f"starting_accounts must be int, got {type(self.starting_accounts).__name__}"
            )
        if self.starting_accounts <= 0:
            raise ValueError(
                f"starting_accounts must be > 0, got {self.starting_accounts}"
            )

        # --- probabilities ---
        for name in (
            "prob_cancel",
            "prob_upgrade",
            "prob_downgrade",
            "prob_feature_add",
            "prob_feature_remove",
            "prob_reactivate",
            "prob_payment_failure",
        ):
            _validate_probability(name, getattr(self, name))

        # --- optional month fields ---
        for name in ("price_increase_month", "duplicate_invoice_line_month"):
            val = getattr(self, name)
            if val is not None:
                if not isinstance(val, int) or isinstance(val, bool):
                    raise TypeError(f"{name} must be int or None")
                if not (1 <= val <= self.months):
                    raise ValueError(
                        f"{name} must be between 1 and months ({self.months}), got {val}"
                    )

        # --- price_increase_amount ---
        if self.price_increase_amount is not None:
            if not isinstance(self.price_increase_amount, Decimal):
                raise TypeError(
                    "price_increase_amount must be Decimal or None"
                )

        # --- price_increase_cancel_lift ---
        if self.price_increase_cancel_lift is not None:
            if isinstance(self.price_increase_cancel_lift, bool):
                raise TypeError("price_increase_cancel_lift must be a number or None")
            if not isinstance(self.price_increase_cancel_lift, (int, float)):
                raise TypeError("price_increase_cancel_lift must be a number or None")
            if self.price_increase_cancel_lift <= 0:
                raise ValueError(
                    f"price_increase_cancel_lift must be positive, got {self.price_increase_cancel_lift}"
                )

        # --- duplicate_invoice_line_probability ---
        if self.duplicate_invoice_line_probability is not None:
            _validate_probability(
                "duplicate_invoice_line_probability",
                self.duplicate_invoice_line_probability,
            )

        # --- coherency groups: all-present or all-absent ---
        self._validate_coherency_groups()

    def _validate_coherency_groups(self) -> None:
        """Enforce that each coherency group is fully populated or fully
        empty.  See module docstring for the design rationale."""
        for group_name, field_names in COHERENCY_GROUPS:
            present = [n for n in field_names if getattr(self, n) is not None]
            absent = [n for n in field_names if getattr(self, n) is None]
            if present and absent:
                raise TypeError(
                    f"Coherency group {group_name!r} is partially specified. "
                    f"Provide all of {list(field_names)} or none. "
                    f"Present: {present}. Missing: {absent}."
                )


def load_scenario_config(path: pathlib.Path) -> ScenarioConfig:
    """Load a ScenarioConfig from a YAML file.

    The YAML file is expected to contain a flat mapping whose keys match
    the ScenarioConfig field names.  Money-compatible fields are parsed
    through ``build_money``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError / TypeError: On invalid content.
    """
    if not path.exists():
        raise FileNotFoundError(f"Scenario config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"Expected a YAML mapping, got {type(raw).__name__}")

    # Convert price_increase_amount through build_money if present.
    if "price_increase_amount" in raw and raw["price_increase_amount"] is not None:
        raw["price_increase_amount"] = build_money(raw["price_increase_amount"])

    return ScenarioConfig(**raw)
