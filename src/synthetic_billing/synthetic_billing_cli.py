"""Minimal demo CLI: baseline population to monthly cancellation to raw emission.

This is a thin command-line wrapper (D35) over the end-to-end path:

    load_scenario_config -> build_default_catalog
    -> RandomStream(config.seed)
    -> build_population       # consumes RNG draws for the starter
                              # population
    -> run_monthly_simulation # consumes further RNG draws for monthly
                              # cancellation selection (D40), and bills
                              # every month against the post-transition
                              # state (D46) — billing consumes no draws
    -> emit_raw_files         # serializes final state, ordered
                              # lifecycle events, and ordered billing
                              # records (D47)

A single :class:`RandomStream` is constructed once and threaded
through both stages so the stream position evolves deterministically
across the full run.

The CLI orchestrates existing functions only.  It does not build the
population or emit files itself, does not implement transitions
other than cancellation, computes no analytics, and loads no database.
Its printed summary reports the emitter's result — the raw artifacts
and their written-row counts, including the invoice and invoice-line
billing files (D47, D48) — but performs no reconciliation of its own:
billing coherence is proven by the tested boundaries and the canonical
smoke gate (D48), not by CLI business logic.  It is a demo runner, not
an application framework.

Default paths are intentionally boring and interpreted relative to the
current working directory:

    --config       configs/baseline_scenario.yaml
    --output-dir   build/raw

Run with::

    python -m synthetic_billing.synthetic_billing_cli
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from synthetic_billing.emit.raw_file_emitter import emit_raw_files
from synthetic_billing.model.catalog_model import build_default_catalog
from synthetic_billing.simulate.month_driver import run_monthly_simulation
from synthetic_billing.simulate.population_builder import build_population
from synthetic_billing.simulate.random_stream import RandomStream
from synthetic_billing.simulate.scenario_config import load_scenario_config

__all__ = ["main"]

# Boring local defaults, interpreted relative to the current working
# directory (not a package resource).  This keeps demo use simple and
# avoids package-resource path complexity for this thin slice.
_DEFAULT_CONFIG: str = "configs/baseline_scenario.yaml"
_DEFAULT_OUTPUT_DIR: str = "build/raw"

# Status code returned when the scenario config file is missing.
_EXIT_CONFIG_MISSING: int = 2


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the demo CLI."""
    parser = argparse.ArgumentParser(
        prog="synthetic-billing",
        description=(
            "Build the deterministic baseline starter population, run "
            "monthly cancellation simulation, generate recurring "
            "account-month invoices, and emit raw operational files "
            "(including invoices.csv and invoice_lines.csv)."
        ),
    )
    parser.add_argument(
        "--config",
        default=_DEFAULT_CONFIG,
        help=(
            "Path to the scenario YAML config, relative to the current "
            "directory. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=_DEFAULT_OUTPUT_DIR,
        help=(
            "Directory to write raw files into, relative to the current "
            "directory. Default: %(default)s"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the baseline generate -> simulate -> raw-emit demo.

    Args:
        argv: Optional argument vector excluding the program name.
            Defaults to ``sys.argv[1:]`` when None.

    Returns:
        Process status code: ``0`` on success, ``2`` if the configured
        scenario file does not exist.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    output_dir = Path(args.output_dir)

    try:
        config = load_scenario_config(config_path)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return _EXIT_CONFIG_MISSING

    catalog = build_default_catalog()
    rng = RandomStream(config.seed)
    starter_state = build_population(config, catalog, rng)
    sim_result = run_monthly_simulation(starter_state, config, rng, catalog)
    emit_result = emit_raw_files(sim_result, output_dir)

    print("Synthetic subscriber billing demo complete.")
    print(f"Output directory: {emit_result.output_dir}")
    print(f"Accounts written: {emit_result.accounts_written}")
    print(f"Subscribers written: {emit_result.subscribers_written}")
    print(f"Subscriptions written: {emit_result.subscriptions_written}")
    print(
        f"Lifecycle events written: {emit_result.lifecycle_events_written}"
    )
    print(f"Lifecycle events file: {emit_result.lifecycle_events_path}")
    print(f"Invoices written: {emit_result.invoices_written}")
    print(f"Invoices file: {emit_result.invoices_path}")
    print(f"Invoice lines written: {emit_result.invoice_lines_written}")
    print(f"Invoice lines file: {emit_result.invoice_lines_path}")
    print(f"Manifest: {emit_result.manifest_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
