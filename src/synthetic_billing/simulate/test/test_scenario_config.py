"""Tests for synthetic_billing.simulate.scenario_config."""

import pathlib
import textwrap
from decimal import Decimal

import pytest

from synthetic_billing.simulate.scenario_config import (
    ScenarioConfig,
    load_scenario_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASELINE_KWARGS = dict(
    seed=42,
    months=12,
    starting_accounts=20,
    prob_cancel=0.04,
    prob_upgrade=0.03,
    prob_downgrade=0.02,
    prob_feature_add=0.05,
    prob_feature_remove=0.03,
    prob_reactivate=0.02,
    prob_payment_failure=0.05,
)


def _make(**overrides) -> ScenarioConfig:
    kw = {**_BASELINE_KWARGS, **overrides}
    return ScenarioConfig(**kw)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestScenarioConfigHappyPath:

    def test_baseline_constructs(self) -> None:
        cfg = _make()
        assert cfg.seed == 42
        assert cfg.months == 12
        assert cfg.starting_accounts == 20

    def test_optional_fields_default_none(self) -> None:
        cfg = _make()
        assert cfg.price_increase_month is None
        assert cfg.price_increase_amount is None
        assert cfg.price_increase_cancel_lift is None
        assert cfg.duplicate_invoice_line_month is None
        assert cfg.duplicate_invoice_line_probability is None

    def test_with_price_increase(self) -> None:
        cfg = _make(
            price_increase_month=6,
            price_increase_amount=Decimal("5.00"),
            price_increase_cancel_lift=0.5,
        )
        assert cfg.price_increase_month == 6
        assert cfg.price_increase_amount == Decimal("5.00")

    def test_with_duplicate_defect(self) -> None:
        cfg = _make(
            duplicate_invoice_line_month=3,
            duplicate_invoice_line_probability=0.1,
        )
        assert cfg.duplicate_invoice_line_month == 3

    def test_frozen(self) -> None:
        cfg = _make()
        with pytest.raises(AttributeError):
            cfg.seed = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


class TestScenarioConfigValidation:

    def test_rejects_bool_seed(self) -> None:
        with pytest.raises(TypeError, match="bool"):
            _make(seed=True)

    def test_rejects_float_seed(self) -> None:
        with pytest.raises(TypeError, match="int"):
            _make(seed=1.5)

    def test_rejects_zero_months(self) -> None:
        with pytest.raises(ValueError, match="months"):
            _make(months=0)

    def test_rejects_negative_months(self) -> None:
        with pytest.raises(ValueError, match="months"):
            _make(months=-1)

    def test_rejects_bool_months(self) -> None:
        with pytest.raises(TypeError, match="months"):
            _make(months=True)  # type: ignore[arg-type]

    def test_rejects_float_months(self) -> None:
        with pytest.raises(TypeError, match="months"):
            _make(months=12.0)  # type: ignore[arg-type]

    def test_rejects_zero_starting_accounts(self) -> None:
        with pytest.raises(ValueError, match="starting_accounts"):
            _make(starting_accounts=0)

    def test_rejects_bool_starting_accounts(self) -> None:
        with pytest.raises(TypeError, match="starting_accounts"):
            _make(starting_accounts=True)  # type: ignore[arg-type]

    def test_rejects_float_starting_accounts(self) -> None:
        with pytest.raises(TypeError, match="starting_accounts"):
            _make(starting_accounts=20.0)  # type: ignore[arg-type]

    def test_rejects_probability_below_zero(self) -> None:
        with pytest.raises(ValueError, match="prob_cancel"):
            _make(prob_cancel=-0.01)

    def test_rejects_probability_above_one(self) -> None:
        with pytest.raises(ValueError, match="prob_upgrade"):
            _make(prob_upgrade=1.01)

    def test_rejects_bool_probability(self) -> None:
        with pytest.raises(TypeError, match="bool"):
            _make(prob_cancel=True)

    def test_rejects_string_probability(self) -> None:
        with pytest.raises(TypeError, match="prob_cancel"):
            _make(prob_cancel="0.04")  # type: ignore[arg-type]

    def test_optional_month_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="price_increase_month"):
            _make(price_increase_month=0)

    def test_optional_month_exceeds_months(self) -> None:
        with pytest.raises(ValueError, match="price_increase_month"):
            _make(price_increase_month=13)

    def test_optional_month_exactly_months_ok(self) -> None:
        # Set all three price_increase fields to satisfy the coherency
        # group; this test focuses on the month range, not coherency.
        cfg = _make(
            price_increase_month=12,
            price_increase_amount=Decimal("1.00"),
            price_increase_cancel_lift=0.1,
        )
        assert cfg.price_increase_month == 12

    def test_optional_month_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="price_increase_month"):
            _make(
                price_increase_month=True,  # type: ignore[arg-type]
                price_increase_amount=Decimal("1.00"),
                price_increase_cancel_lift=0.1,
            )

    def test_duplicate_optional_month_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="duplicate_invoice_line_month"):
            _make(
                duplicate_invoice_line_month=3.5,  # type: ignore[arg-type]
                duplicate_invoice_line_probability=0.1,
            )

    def test_price_increase_cancel_lift_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _make(price_increase_cancel_lift=0.0)

    def test_price_increase_cancel_lift_rejects_bool(self) -> None:
        with pytest.raises(TypeError, match="price_increase_cancel_lift"):
            _make(
                price_increase_month=6,
                price_increase_amount=Decimal("1.00"),
                price_increase_cancel_lift=True,  # type: ignore[arg-type]
            )

    def test_price_increase_cancel_lift_rejects_string(self) -> None:
        with pytest.raises(TypeError, match="price_increase_cancel_lift"):
            _make(
                price_increase_month=6,
                price_increase_amount=Decimal("1.00"),
                price_increase_cancel_lift="0.5",  # type: ignore[arg-type]
            )

    def test_duplicate_probability_validated(self) -> None:
        with pytest.raises(ValueError, match="duplicate_invoice_line_probability"):
            _make(
                duplicate_invoice_line_month=1,
                duplicate_invoice_line_probability=1.5,
            )

    def test_price_increase_amount_rejects_raw_string(self) -> None:
        """Direct construction requires Decimal or None, not str."""
        with pytest.raises(TypeError, match="Decimal"):
            _make(
                price_increase_month=6,
                price_increase_amount="5.00",  # type: ignore[arg-type]
            )

    def test_price_increase_amount_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="Decimal"):
            _make(
                price_increase_month=6,
                price_increase_amount=5.0,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# Coherency groups
# ---------------------------------------------------------------------------


class TestScenarioConfigCoherency:
    """Optional scenario knob groups must be all-present or all-absent."""

    # -- price_increase group: month + amount + cancel_lift --

    def test_price_increase_all_present_ok(self) -> None:
        cfg = _make(
            price_increase_month=6,
            price_increase_amount=Decimal("5.00"),
            price_increase_cancel_lift=0.5,
        )
        assert cfg.price_increase_month == 6

    def test_price_increase_all_absent_ok(self) -> None:
        cfg = _make()  # baseline has none of them
        assert cfg.price_increase_month is None
        assert cfg.price_increase_amount is None
        assert cfg.price_increase_cancel_lift is None

    def test_price_increase_month_alone_rejected(self) -> None:
        with pytest.raises(TypeError, match="price_increase"):
            _make(price_increase_month=6)

    def test_price_increase_amount_alone_rejected(self) -> None:
        with pytest.raises(TypeError, match="price_increase"):
            _make(price_increase_amount=Decimal("5.00"))

    def test_price_increase_cancel_lift_alone_rejected(self) -> None:
        with pytest.raises(TypeError, match="price_increase"):
            _make(price_increase_cancel_lift=0.5)

    def test_price_increase_month_and_amount_without_lift_rejected(self) -> None:
        with pytest.raises(TypeError, match="price_increase"):
            _make(
                price_increase_month=6,
                price_increase_amount=Decimal("5.00"),
            )

    def test_price_increase_month_and_lift_without_amount_rejected(self) -> None:
        with pytest.raises(TypeError, match="price_increase"):
            _make(
                price_increase_month=6,
                price_increase_cancel_lift=0.5,
            )

    # -- duplicate_invoice_line_defect group: month + probability --

    def test_duplicate_invoice_line_both_present_ok(self) -> None:
        cfg = _make(
            duplicate_invoice_line_month=3,
            duplicate_invoice_line_probability=0.1,
        )
        assert cfg.duplicate_invoice_line_month == 3

    def test_duplicate_invoice_line_both_absent_ok(self) -> None:
        cfg = _make()
        assert cfg.duplicate_invoice_line_month is None
        assert cfg.duplicate_invoice_line_probability is None

    def test_duplicate_invoice_line_month_alone_rejected(self) -> None:
        with pytest.raises(TypeError, match="duplicate_invoice_line_defect"):
            _make(duplicate_invoice_line_month=3)

    def test_duplicate_invoice_line_probability_alone_rejected(self) -> None:
        with pytest.raises(TypeError, match="duplicate_invoice_line_defect"):
            _make(duplicate_invoice_line_probability=0.1)

    # -- groups are independent --

    def test_groups_are_independent(self) -> None:
        """Setting one full group should not require the other."""
        cfg = _make(
            price_increase_month=6,
            price_increase_amount=Decimal("5.00"),
            price_increase_cancel_lift=0.5,
        )
        assert cfg.duplicate_invoice_line_month is None


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


class TestLoadScenarioConfig:

    def test_loads_baseline_yaml(self) -> None:
        cfg_path = (
            pathlib.Path(__file__).resolve().parents[4]
            / "configs"
            / "baseline_scenario.yaml"
        )
        cfg = load_scenario_config(cfg_path)
        assert cfg.seed == 42
        assert cfg.months == 12

    def test_loads_from_tmp(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "test_scenario.yaml"
        p.write_text(
            textwrap.dedent("""\
                seed: 1
                months: 6
                starting_accounts: 5
                prob_cancel: 0.0
                prob_upgrade: 0.0
                prob_downgrade: 0.0
                prob_feature_add: 0.0
                prob_feature_remove: 0.0
                prob_reactivate: 0.0
                prob_payment_failure: 0.0
            """),
            encoding="utf-8",
        )
        cfg = load_scenario_config(p)
        assert cfg.seed == 1

    def test_file_not_found(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_scenario_config(tmp_path / "no_such_file.yaml")

    def test_non_mapping_raises(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("- list\n- not\n- mapping\n", encoding="utf-8")
        with pytest.raises(TypeError, match="mapping"):
            load_scenario_config(p)

    def test_loads_with_price_increase_amount(self, tmp_path: pathlib.Path) -> None:
        p = tmp_path / "price.yaml"
        p.write_text(
            textwrap.dedent("""\
                seed: 7
                months: 12
                starting_accounts: 10
                prob_cancel: 0.04
                prob_upgrade: 0.03
                prob_downgrade: 0.02
                prob_feature_add: 0.05
                prob_feature_remove: 0.03
                prob_reactivate: 0.02
                prob_payment_failure: 0.05
                price_increase_month: 6
                price_increase_amount: "5.00"
                price_increase_cancel_lift: 0.5
            """),
            encoding="utf-8",
        )
        cfg = load_scenario_config(p)
        assert cfg.price_increase_amount == Decimal("5.00")
