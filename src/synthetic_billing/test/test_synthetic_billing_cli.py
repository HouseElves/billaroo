"""Tests for synthetic_billing_cli.py.

Exercises the thin demo CLI (D35): success path and exit code, emitted
files and manifest counts (cross-checked against an independent build),
the printed summary, rerun determinism, missing-config handling, bad
argument handling, and cwd-relative default paths.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from synthetic_billing import synthetic_billing_cli as cli
from synthetic_billing.emit.manifest_emitter import MANIFEST_FILENAME
from synthetic_billing.emit.raw_file_emitter import (
    ACCOUNTS_FILENAME,
    LIFECYCLE_EVENTS_FILENAME,
    SUBSCRIBERS_FILENAME,
    SUBSCRIPTIONS_FILENAME,
)
from synthetic_billing.model.catalog_model import build_default_catalog
from synthetic_billing.simulate.month_driver import run_monthly_simulation
from synthetic_billing.simulate.population_builder import build_population
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import load_scenario_config

# Real baseline config from the repo, located relative to this test
# file so the path is independent of the working directory.
# parents: [0]=test, [1]=synthetic_billing, [2]=src, [3]=repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_CONFIG = _REPO_ROOT / "configs" / "baseline_scenario.yaml"

# Field mapping for a small self-contained config, used where the test
# must own the file (e.g. the cwd-relative default-path test).  Built
# as a dict and dumped to YAML so it shares no literal text with other
# test modules' inline config fixtures.
_MINIMAL_CONFIG_FIELDS = {
    "seed": 7,
    "months": 3,
    "starting_accounts": 4,
    "prob_cancel": 0.0,
    "prob_upgrade": 0.0,
    "prob_downgrade": 0.0,
    "prob_feature_add": 0.0,
    "prob_feature_remove": 0.0,
    "prob_reactivate": 0.0,
    "prob_payment_failure": 0.0,
}


def _baseline_args(output_dir: Path) -> list[str]:
    """Argument vector running the real baseline config into *output_dir*."""
    return [
        "--config", str(_BASELINE_CONFIG),
        "--output-dir", str(output_dir),
    ]


def _manifest_counts(output_dir: Path) -> dict[str, int]:
    """Return ``{filename: record_count}`` from the emitted manifest."""
    manifest = json.loads(
        (output_dir / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    return {item["name"]: item["record_count"] for item in manifest["files"]}


def _read_all_bytes(output_dir: Path) -> dict[str, bytes]:
    """Return ``{filename: bytes}`` for all five emitted artifacts."""
    names = (
        ACCOUNTS_FILENAME, SUBSCRIBERS_FILENAME,
        SUBSCRIPTIONS_FILENAME, LIFECYCLE_EVENTS_FILENAME,
        MANIFEST_FILENAME,
    )
    return {name: (output_dir / name).read_bytes() for name in names}


def _independent_counts(config_path: Path) -> tuple[int, int, int]:
    """Build the full pipeline independently and return final-state tuple lengths.

    Mirrors the CLI's orchestration — population construction followed
    by monthly cancellation simulation — so a test can cross-check the
    manifest's final-state tuple counts against the lengths produced
    by an independent complete pipeline run.  The cross-check does not
    discriminate between the CLI emitting final-state versus
    starter-state values: in the current cancellation-only feature
    set, cancellation deactivates a subscriber and ends its
    subscriptions but never removes rows, so the starter-state and
    final-state tuple lengths happen to be equal.
    """
    config = load_scenario_config(config_path)
    rng = RandomStream(config.seed)
    starter = build_population(config, build_default_catalog(), rng)
    result = run_monthly_simulation(starter, config, rng)
    return (
        len(result.state.accounts),
        len(result.state.subscribers),
        len(result.state.subscriptions),
    )


# ---- success path ----

class TestCliSuccess:
    """The CLI runs the baseline path and reports success."""

    def test_returns_zero(self, tmp_path) -> None:
        """main returns 0 on a successful run."""
        assert cli.main(_baseline_args(tmp_path)) == 0

    def test_emits_all_files(self, tmp_path) -> None:
        """All five raw artifacts are written to the output directory."""
        cli.main(_baseline_args(tmp_path))
        assert (tmp_path / ACCOUNTS_FILENAME).exists()
        assert (tmp_path / SUBSCRIBERS_FILENAME).exists()
        assert (tmp_path / SUBSCRIPTIONS_FILENAME).exists()
        assert (tmp_path / LIFECYCLE_EVENTS_FILENAME).exists()
        assert (tmp_path / MANIFEST_FILENAME).exists()

    def test_manifest_counts_match_independent_build(self, tmp_path) -> None:
        """Manifest counts equal an independently built population."""
        cli.main(_baseline_args(tmp_path))
        counts = _manifest_counts(tmp_path)
        accounts, subscribers, subscriptions = _independent_counts(
            _BASELINE_CONFIG
        )
        assert counts[ACCOUNTS_FILENAME] == accounts
        assert counts[SUBSCRIBERS_FILENAME] == subscribers
        assert counts[SUBSCRIPTIONS_FILENAME] == subscriptions

    def test_accounts_match_starting_accounts(self, tmp_path) -> None:
        """Account and subscriber counts equal the config starting_accounts."""
        config = load_scenario_config(_BASELINE_CONFIG)
        cli.main(_baseline_args(tmp_path))
        counts = _manifest_counts(tmp_path)
        assert counts[ACCOUNTS_FILENAME] == config.starting_accounts
        assert counts[SUBSCRIBERS_FILENAME] == config.starting_accounts


# ---- summary output ----

class TestCliSummary:
    """The printed summary is human-readable and informative."""

    def test_summary_includes_output_dir_and_counts(
        self, tmp_path, capsys
    ) -> None:
        """Summary names the output directory and the three final-state record counts.

        The lifecycle-event count is covered by a separate test below.
        """
        cli.main(_baseline_args(tmp_path))
        out = capsys.readouterr().out
        accounts, subscribers, subscriptions = _independent_counts(
            _BASELINE_CONFIG
        )
        assert str(tmp_path) in out
        assert f"Accounts written: {accounts}" in out
        assert f"Subscribers written: {subscribers}" in out
        assert f"Subscriptions written: {subscriptions}" in out

    def test_summary_includes_manifest_path(self, tmp_path, capsys) -> None:
        """Summary names the emitted manifest path."""
        cli.main(_baseline_args(tmp_path))
        out = capsys.readouterr().out
        assert str(tmp_path / MANIFEST_FILENAME) in out


# ---- determinism ----

class TestCliDeterminism:
    """Reruns are deterministic under the overwrite policy."""

    def test_rerun_same_dir_byte_identical(self, tmp_path) -> None:
        """Running twice into the same dir yields byte-identical files."""
        args = _baseline_args(tmp_path)
        cli.main(args)
        first = _read_all_bytes(tmp_path)
        cli.main(args)
        assert _read_all_bytes(tmp_path) == first

    def test_separate_dirs_identical_content(self, tmp_path) -> None:
        """Two runs into different dirs produce identical file content."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        cli.main(_baseline_args(dir_a))
        cli.main(_baseline_args(dir_b))
        assert _read_all_bytes(dir_a) == _read_all_bytes(dir_b)


# ---- error handling ----

class TestCliErrors:
    """Invalid inputs are handled explicitly."""

    def test_missing_config_returns_nonzero(self, tmp_path, capsys) -> None:
        """A missing config path returns a nonzero status and warns."""
        missing = tmp_path / "does_not_exist.yaml"
        code = cli.main(
            ["--config", str(missing), "--output-dir", str(tmp_path)]
        )
        assert code != 0
        assert "not found" in capsys.readouterr().err

    def test_unknown_argument_raises_systemexit(self) -> None:
        """An unrecognized argument makes argparse raise SystemExit."""
        with pytest.raises(SystemExit):
            cli.main(["--bogus"])


# ---- default paths ----

class TestCliDefaultPaths:
    """Default paths resolve relative to the current working directory."""

    def test_defaults_relative_to_cwd(self, tmp_path, monkeypatch) -> None:
        """With no args, defaults read configs/ and write build/raw under cwd."""
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        (config_dir / "baseline_scenario.yaml").write_text(
            yaml.safe_dump(_MINIMAL_CONFIG_FIELDS), encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        code = cli.main([])

        assert code == 0
        assert (tmp_path / "build" / "raw" / MANIFEST_FILENAME).exists()
        assert (tmp_path / "build" / "raw" / ACCOUNTS_FILENAME).exists()

    def test_default_output_dir_under_cwd(self, tmp_path, monkeypatch) -> None:
        """With only --config given, output defaults to build/raw under cwd."""
        monkeypatch.chdir(tmp_path)
        code = cli.main(["--config", str(_BASELINE_CONFIG)])
        assert code == 0
        assert (tmp_path / "build" / "raw" / MANIFEST_FILENAME).exists()


# ---- monthly simulation integration (Slice 3) ----


def _independent_event_count(config_path: Path) -> int:
    """Run the full pipeline independently and return the event count.

    Mirrors the CLI's orchestration so the test does not pin to a
    hard-coded value the production code is forbidden from carrying.
    """
    config = load_scenario_config(config_path)
    rng = RandomStream(config.seed)
    state = build_population(config, build_default_catalog(), rng)
    result = run_monthly_simulation(state, config, rng)
    return len(result.lifecycle_events)


class TestCliMonthlySimulationIntegration:
    """The CLI runs the monthly simulation and emits lifecycle_events.csv."""

    def test_lifecycle_events_file_created(self, tmp_path) -> None:
        """The baseline CLI run produces lifecycle_events.csv."""
        cli.main(_baseline_args(tmp_path))
        assert (tmp_path / LIFECYCLE_EVENTS_FILENAME).exists()

    def test_manifest_lists_lifecycle_events(self, tmp_path) -> None:
        """The manifest includes lifecycle_events.csv with a record count."""
        cli.main(_baseline_args(tmp_path))
        counts = _manifest_counts(tmp_path)
        assert LIFECYCLE_EVENTS_FILENAME in counts

    def test_manifest_event_count_matches_independent_run(
        self, tmp_path,
    ) -> None:
        """Manifest event count equals an independent pipeline run."""
        cli.main(_baseline_args(tmp_path))
        counts = _manifest_counts(tmp_path)
        expected = _independent_event_count(_BASELINE_CONFIG)
        assert counts[LIFECYCLE_EVENTS_FILENAME] == expected

    def test_summary_includes_lifecycle_event_count(
        self, tmp_path, capsys,
    ) -> None:
        """Summary names the lifecycle event count emitted."""
        cli.main(_baseline_args(tmp_path))
        out = capsys.readouterr().out
        expected = _independent_event_count(_BASELINE_CONFIG)
        assert f"Lifecycle events written: {expected}" in out

    def test_summary_includes_lifecycle_event_path(
        self, tmp_path, capsys,
    ) -> None:
        """Summary names the emitted lifecycle events file path."""
        cli.main(_baseline_args(tmp_path))
        out = capsys.readouterr().out
        assert str(tmp_path / LIFECYCLE_EVENTS_FILENAME) in out
