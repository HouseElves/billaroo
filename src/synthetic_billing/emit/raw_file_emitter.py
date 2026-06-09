"""Raw operational file emission.

Serializes an already-built in-memory ``SimulationState`` (D33) into
raw CSV operational files plus a JSON manifest under a caller-provided
output directory.

This is the raw operational layer (D8, D34): the emitter writes only
records that already exist in the state.  It does not simulate
lifecycle actions, does not compute analytic marts or reconstruct
business metrics, and does not load any database.  It does not mutate
the input state.

Determinism (D2):

- stable file names (module constants below),
- stable column order (the explicit ``*_COLUMNS`` tuples),
- stable row order (the order records appear in the state tuples),
- stable newline behavior (Unix ``"\n"``),
- a stable manifest (see ``manifest_emitter``).

Serialization is the boring stdlib default: ``csv`` renders ``bool``
as ``"True"`` / ``"False"`` and ``None`` (an open ``end_month``) as an
empty field.

Overwrite policy: existing target files are overwritten
deterministically.  Re-running emission on an unchanged state
reproduces byte-identical files, so a rerun is safe and idempotent.

Stdlib only: ``csv``, ``dataclasses``, ``pathlib``.
"""

from __future__ import annotations

import csv
import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from synthetic_billing.emit.manifest_emitter import emit_manifest
from synthetic_billing.simulate.simulation_state import SimulationState

__all__ = [
    "ACCOUNTS_FILENAME",
    "SUBSCRIBERS_FILENAME",
    "SUBSCRIPTIONS_FILENAME",
    "ACCOUNT_COLUMNS",
    "SUBSCRIBER_COLUMNS",
    "SUBSCRIPTION_COLUMNS",
    "RawEmissionResult",
    "emit_raw_files",
]

ACCOUNTS_FILENAME: str = "accounts.csv"
SUBSCRIBERS_FILENAME: str = "subscribers.csv"
SUBSCRIPTIONS_FILENAME: str = "subscriptions.csv"

# Declared grain (constitution rule 15) for the artifacts this slice
# emits.  These are starter-population snapshots; there is no time
# dimension yet because D33 produces only the initial in-memory state.
#
# - accounts.csv:      one row per Account in SimulationState.accounts
#                      for the emitted starter population snapshot.
# - subscribers.csv:   one row per Subscriber in
#                      SimulationState.subscribers for the emitted
#                      starter population snapshot.
# - subscriptions.csv: one row per Subscription in
#                      SimulationState.subscriptions for the emitted
#                      starter population snapshot.
#
# When later slices add a month dimension and lifecycle records, the
# grain of these artifacts is revisited (e.g. one account per snapshot
# month) rather than silently changed.

# Explicit column orders.  These mirror the contract dataclass fields
# exactly (account_contracts.Account, subscriber_contracts.Subscriber,
# subscription_contracts.Subscription) and are declared explicitly
# rather than derived so the raw schema is a deliberate, reviewable
# choice and not an accident of field ordering.
ACCOUNT_COLUMNS: tuple[str, ...] = (
    "account_id",
    "account_ordinal",
    "billing_cycle_day",
    "region_code",
    "account_status",
)
SUBSCRIBER_COLUMNS: tuple[str, ...] = (
    "subscriber_id",
    "account_id",
    "subscriber_ordinal",
    "plan_code",
    "active",
)
SUBSCRIPTION_COLUMNS: tuple[str, ...] = (
    "subscription_id",
    "subscriber_id",
    "item_type",
    "item_code",
    "start_month",
    "end_month",
    "subscription_status",
)


# RawEmissionResult is a pure internal return summary.  Every field is
# produced by this module from trusted inputs, so it does not need the
# _Validated vocabulary (D30) — a plain frozen dataclass is enough
# (constitution rule 22).  If a future slice turns this into a public
# boundary read by untrusted callers, revisit and adopt _Validated.
#
# The eight attributes (four paths + the output dir + three counts) are
# the natural shape of a batch summary; collapsing them into nested
# sub-objects would obscure the result rather than clarify it.
@dataclasses.dataclass(frozen=True)
class RawEmissionResult:  # pylint: disable=too-many-instance-attributes
    """Summary of a single raw-emission batch.

    Attributes:
        output_dir: Directory the batch was written into.
        accounts_path: Path to the emitted ``accounts.csv``.
        subscribers_path: Path to the emitted ``subscribers.csv``.
        subscriptions_path: Path to the emitted ``subscriptions.csv``.
        manifest_path: Path to the emitted ``manifest.json``.
        accounts_written: Account rows written (excludes the header).
        subscribers_written: Subscriber rows written.
        subscriptions_written: Subscription rows written.
    """

    output_dir: Path
    accounts_path: Path
    subscribers_path: Path
    subscriptions_path: Path
    manifest_path: Path
    accounts_written: int
    subscribers_written: int
    subscriptions_written: int


def emit_raw_files(
    state: SimulationState,
    output_dir: Path,
) -> RawEmissionResult:
    """Emit raw operational CSV files and a manifest for *state*.

    Creates *output_dir* (and any missing parents) if it does not
    already exist, then writes ``accounts.csv``, ``subscribers.csv``,
    ``subscriptions.csv``, and ``manifest.json``.  Existing files are
    overwritten deterministically.

    The input *state* is not mutated.

    Args:
        state: The in-memory population to serialize.
        output_dir: Directory to write the raw batch into.

    Returns:
        A :class:`RawEmissionResult` summarizing the written batch.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    accounts_path = output_dir / ACCOUNTS_FILENAME
    subscribers_path = output_dir / SUBSCRIBERS_FILENAME
    subscriptions_path = output_dir / SUBSCRIPTIONS_FILENAME

    accounts_written = _write_csv(
        accounts_path, ACCOUNT_COLUMNS, state.accounts,
    )
    subscribers_written = _write_csv(
        subscribers_path, SUBSCRIBER_COLUMNS, state.subscribers,
    )
    subscriptions_written = _write_csv(
        subscriptions_path, SUBSCRIPTION_COLUMNS, state.subscriptions,
    )

    manifest_path = emit_manifest(
        output_dir,
        (
            (ACCOUNTS_FILENAME, accounts_written),
            (SUBSCRIBERS_FILENAME, subscribers_written),
            (SUBSCRIPTIONS_FILENAME, subscriptions_written),
        ),
    )

    return RawEmissionResult(
        output_dir=output_dir,
        accounts_path=accounts_path,
        subscribers_path=subscribers_path,
        subscriptions_path=subscriptions_path,
        manifest_path=manifest_path,
        accounts_written=accounts_written,
        subscribers_written=subscribers_written,
        subscriptions_written=subscriptions_written,
    )


def _write_csv(
    path: Path,
    columns: tuple[str, ...],
    records: Sequence[Any],
) -> int:
    """Write *records* to *path* as CSV and return the row count.

    The header row is the *columns* tuple; each data row pulls the
    same-named attributes off each record in *records* order.  Rows
    are written with Unix newlines.  The header is not counted in the
    return value.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for record in records:
            writer.writerow([getattr(record, column) for column in columns])
    return len(records)
