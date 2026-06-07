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

_BASELINE_KWARGS = {
    "seed": 42,
    "months": 12,
    "starting_accounts": 20,
    "prob_cancel": 0.04,
    "prob_upgrade": 0.03,
    "prob_downgrade": 0.02,
    "prob_feature_add": 0.05,
    "prob_feature_remove": 0.03,
    "prob_reactivate": 0.02,
    "prob_payment_failure": 0.05,
}


def _make(**overrides) -> ScenarioConfig:
    """Build a ScenarioConfig with baseline values, applying *overrides*."""
    kw = {**_BASELINE_KWARGS, **overrides}
    return ScenarioConfig(**kw)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestScenarioConfigHappyPath:
    """ScenarioConfig stores a valid baseline and optional knobs."""

    def test_baseline_constructs(self) -> None:
        """Required fields are stored unchanged."""
        cfg = _make()
        assert cfg.seed == 42
        assert cfg.months == 12
        assert cfg.starting_accounts == 20

    def test_optional_fields_default_none(self) -> None:
        """Omitted optional fields default to None."""
        cfg = _make()
        assert cfg.price_increase_month is None
        assert cfg.price_increase_amount is None
        assert cfg.price_increase_cancel_lift is None
        assert cfg.duplicate_invoice_line_month is None
        assert cfg.duplicate_invoice_line_probability is None

    def test_with_price_increase(self) -> None:
        """All three price-increase fields accepted together."""
        cfg = _make(
            price_increase_month=6,
            price_increase_amount=Decimal("5.00"),
            price_increase_cancel_lift=0.5,
        )
        assert cfg.price_increase_month == 6
        assert cfg.price_increase_amount == Decimal("5.00")

    def test_with_duplicate_defect(self) -> None:
        """Both duplicate-defect fields accepted together."""
        cfg = _make(
            duplicate_invoice_line_month=3,
            duplicate_invoice_line_probability=0.1,
        )
        assert cfg.duplicate_invoice_line_month == 3

    def test_frozen(self) -> None:
        """Mutation raises AttributeError on the frozen dataclass."""
        cfg = _make()
        with pytest.raises(AttributeError):
            cfg.seed = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


class TestScenarioConfigValidation:  # pylint: disable=too-many-public-methods
    """ScenarioConfig rejects invalid types, ranges, and shapes."""

    def test_rejects_bool_seed(self) -> None:
        """Bool is not a valid seed."""
        with pytest.raises(TypeError, match="bool"):
            _make(seed=True)

    def test_rejects_float_seed(self) -> None:
        """Float is not a valid seed."""
        with pytest.raises(TypeError, match="int"):
            _make(seed=1.5)

    def test_rejects_zero_months(self) -> None:
        """Months must be positive."""
        with pytest.raises(ValueError, match="months"):
            _make(months=0)

    def test_rejects_negative_months(self) -> None:
        """Negative months are invalid."""
        with pytest.raises(ValueError, match="months"):
            _make(months=-1)

    def test_rejects_bool_months(self) -> None:
        """Bool is not a valid months value."""
        with pytest.raises(TypeError, match="months"):
            _make(months=True)  # type: ignore[arg-type]

    def test_rejects_float_months(self) -> None:
        """Float is not a valid months value."""
        with pytest.raises(TypeError, match="months"):
            _make(months=12.0)  # type: ignore[arg-type]

    def test_rejects_zero_starting_accounts(self) -> None:
        """Starting accounts must be positive."""
        with pytest.raises(ValueError, match="starting_accounts"):
            _make(starting_accounts=0)

    def test_rejects_bool_starting_accounts(self) -> None:
        """Bool is not a valid starting_accounts value."""
        with pytest.raises(TypeError, match="starting_accounts"):
            _make(starting_accounts=True)  # type: ignore[arg-type]

    def test_rejects_float_starting_accounts(self) -> None:
        """Float is not a valid starting_accounts value."""
        with pytest.raises(TypeError, match="starting_accounts"):
            _make(starting_accounts=20.0)  # type: ignore[arg-type]

    def test_rejects_probability_below_zero(self) -> None:
        """Probabilities must be at least 0."""
        with pytest.raises(ValueError, match="prob_cancel"):
            _make(prob_cancel=-0.01)

    def test_rejects_probability_above_one(self) -> None:
        """Probabilities must be at most 1."""
        with pytest.raises(ValueError, match="prob_upgrade"):
            _make(prob_upgrade=1.01)

    def test_rejects_bool_probability(self) -> None:
        """Bool is not a valid probability."""
        with pytest.raises(TypeError, match="bool"):
            _make(prob_cancel=True)

    def test_rejects_string_probability(self) -> None:
        """String is not a valid probability."""
        with pytest.raises(TypeError, match="prob_cancel"):
            _make(prob_cancel="0.04")  # type: ignore[arg-type]

    def test_optional_month_zero_rejected(self) -> None:
        """Optional month fields must be >= 1."""
        with pytest.raises(ValueError, match="price_increase_month"):
            _make(price_increase_month=0)

    def test_optional_month_exceeds_months(self) -> None:
        """Optional month fields must be <= months."""
        with pytest.raises(ValueError, match="price_increase_month"):
            _make(price_increase_month=13)

    def test_optional_month_exactly_months_ok(self) -> None:
        """A month equal to the scenario length is valid."""
        cfg = _make(
            price_increase_month=12,
            price_increase_amount=Decimal("1.00"),
            price_increase_cancel_lift=0.1,
        )
        assert cfg.price_increase_month == 12

    def test_optional_month_rejects_bool(self) -> None:
        """Bool is not a valid optional month."""
        with pytest.raises(TypeError, match="price_increase_month"):
            _make(
                price_increase_month=True,  # type: ignore[arg-type]
                price_increase_amount=Decimal("1.00"),
                price_increase_cancel_lift=0.1,
            )

    def test_duplicate_optional_month_rejects_float(self) -> None:
        """Float is not a valid optional month."""
        with pytest.raises(TypeError, match="duplicate_invoice_line_month"):
            _make(
                duplicate_invoice_line_month=3.5,  # type: ignore[arg-type]
                duplicate_invoice_line_probability=0.1,
            )

    def test_price_increase_cancel_lift_must_be_positive(self) -> None:
        """Cancel lift must be strictly positive."""
        with pytest.raises(ValueError, match="positive"):
            _make(price_increase_cancel_lift=0.0)

    def test_price_increase_cancel_lift_rejects_bool(self) -> None:
        """Bool is not a valid cancel lift."""
        with pytest.raises(TypeError, match="price_increase_cancel_lift"):
            _make(
                price_increase_month=6,
                price_increase_amount=Decimal("1.00"),
                price_increase_cancel_lift=True,  # type: ignore[arg-type]
            )

    def test_price_increase_cancel_lift_rejects_string(self) -> None:
        """String is not a valid cancel lift."""
        with pytest.raises(TypeError, match="price_increase_cancel_lift"):
            _make(
                price_increase_month=6,
                price_increase_amount=Decimal("1.00"),
                price_increase_cancel_lift="0.5",  # type: ignore[arg-type]
            )

    def test_duplicate_probability_validated(self) -> None:
        """Duplicate-defect probability must be in [0, 1]."""
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
        """Direct construction requires Decimal or None, not float."""
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
        """All three price-increase fields present is valid."""
        cfg = _make(
            price_increase_month=6,
            price_increase_amount=Decimal("5.00"),
            price_increase_cancel_lift=0.5,
        )
        assert cfg.price_increase_month == 6

    def test_price_increase_all_absent_ok(self) -> None:
        """All three price-increase fields absent is valid."""
        cfg = _make()
        assert cfg.price_increase_month is None
        assert cfg.price_increase_amount is None
        assert cfg.price_increase_cancel_lift is None

    def test_price_increase_month_alone_rejected(self) -> None:
        """Month without amount and lift is partial."""
        with pytest.raises(TypeError, match="price_increase"):
            _make(price_increase_month=6)

    def test_price_increase_amount_alone_rejected(self) -> None:
        """Amount without month and lift is partial."""
        with pytest.raises(TypeError, match="price_increase"):
            _make(price_increase_amount=Decimal("5.00"))

    def test_price_increase_cancel_lift_alone_rejected(self) -> None:
        """Cancel lift without month and amount is partial."""
        with pytest.raises(TypeError, match="price_increase"):
            _make(price_increase_cancel_lift=0.5)

    def test_price_increase_month_and_amount_without_lift_rejected(self) -> None:
        """Two of three is still partial."""
        with pytest.raises(TypeError, match="price_increase"):
            _make(
                price_increase_month=6,
                price_increase_amount=Decimal("5.00"),
            )

    def test_price_increase_month_and_lift_without_amount_rejected(self) -> None:
        """Two of three is still partial."""
        with pytest.raises(TypeError, match="price_increase"):
            _make(
                price_increase_month=6,
                price_increase_cancel_lift=0.5,
            )

    # -- duplicate_invoice_line_defect group: month + probability --

    def test_duplicate_invoice_line_both_present_ok(self) -> None:
        """Both duplicate-defect fields present is valid."""
        cfg = _make(
            duplicate_invoice_line_month=3,
            duplicate_invoice_line_probability=0.1,
        )
        assert cfg.duplicate_invoice_line_month == 3

    def test_duplicate_invoice_line_both_absent_ok(self) -> None:
        """Both duplicate-defect fields absent is valid."""
        cfg = _make()
        assert cfg.duplicate_invoice_line_month is None
        assert cfg.duplicate_invoice_line_probability is None

    def test_duplicate_invoice_line_month_alone_rejected(self) -> None:
        """Month without probability is partial."""
        with pytest.raises(TypeError, match="duplicate_invoice_line_defect"):
            _make(duplicate_invoice_line_month=3)

    def test_duplicate_invoice_line_probability_alone_rejected(self) -> None:
        """Probability without month is partial."""
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
    """load_scenario_config reads a YAML file into a ScenarioConfig."""

    def test_loads_baseline_yaml(self) -> None:
        """The shipped baseline_scenario.yaml round-trips cleanly."""
        cfg_path = (
            pathlib.Path(__file__).resolve().parents[4]
            / "configs"
            / "baseline_scenario.yaml"
        )
        cfg = load_scenario_config(cfg_path)
        assert cfg.seed == 42
        assert cfg.months == 12

    def test_loads_from_tmp(self, tmp_path: pathlib.Path) -> None:
        """A minimal scenario written to a temp file loads correctly."""
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
        """A missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_scenario_config(tmp_path / "no_such_file.yaml")

    def test_non_mapping_raises(self, tmp_path: pathlib.Path) -> None:
        """A YAML list instead of a mapping raises TypeError."""
        p = tmp_path / "bad.yaml"
        p.write_text("- list\n- not\n- mapping\n", encoding="utf-8")
        with pytest.raises(TypeError, match="mapping"):
            load_scenario_config(p)

    def test_loads_with_price_increase_amount(self, tmp_path: pathlib.Path) -> None:
        """Quoted string price_increase_amount is routed through build_money."""
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
