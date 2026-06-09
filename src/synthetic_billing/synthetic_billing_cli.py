"""Minimal demo CLI: baseline population to raw emission.

This is a thin command-line wrapper (D35) over the existing baseline
path:

    load_scenario_config -> build_default_catalog
    -> RandomStream(config.seed) -> build_population -> emit_raw_files

It orchestrates existing functions only.  It does not build the
population or emit files itself, does not simulate lifecycle changes,
does not create invoices / payments / usage / account actions,
computes no analytics, and loads no database.  It is a demo runner,
not an application framework.

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
            "Build the deterministic baseline starter population and "
            "emit raw operational files."
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
    """Run the baseline generate -> raw-emit demo.

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
    state = build_population(config, catalog, rng)
    result = emit_raw_files(state, output_dir)

    print("Synthetic subscriber billing demo complete.")
    print(f"Output directory: {result.output_dir}")
    print(f"Accounts written: {result.accounts_written}")
    print(f"Subscribers written: {result.subscribers_written}")
    print(f"Subscriptions written: {result.subscriptions_written}")
    print(f"Manifest: {result.manifest_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
