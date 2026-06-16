"""Raw operational file emission.

Serializes an already-built :class:`SimulationResult` (D40, D46) into
raw CSV operational files plus a JSON manifest under a caller-provided
output directory.

This is the raw operational layer (D8, D34): the emitter writes only
records that already exist in the simulation result.  It does not
simulate lifecycle actions, does not compute subscription chargeability
or catalog pricing, does not construct invoices or reconcile totals,
does not orchestrate monthly billing, does not compute analytic marts
or reconstruct business metrics, and does not load any database.  It
does not mutate the input result.  The billing records it writes
(``invoices.csv``, ``invoice_lines.csv``, D47) are serialized exactly
as the simulation run already produced them (D46).

Determinism (D2):

- stable file names (module constants below),
- stable column order (the explicit ``*_COLUMNS`` tuples),
- stable row order (the order records appear in the state tuples and
  in the simulation result's lifecycle-event, invoice, and
  invoice-line tuples),
- stable newline behavior (Unix ``"\n"``),
- a stable manifest (see ``manifest_emitter``).

Serialization is the boring stdlib default: ``csv`` renders ``bool``
as ``"True"`` / ``"False"`` and ``None`` (an open ``end_month``) as an
empty field.  Monetary ``Decimal`` values render through ``str`` as
exact decimal text (e.g. ``"29.99"``), never through binary floating
point (D13, D47).

Overwrite policy: existing target files are overwritten
deterministically.  Re-running emission on an unchanged result
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
from synthetic_billing.simulate.simulation_result import SimulationResult

__all__ = [
    "ACCOUNTS_FILENAME",
    "SUBSCRIBERS_FILENAME",
    "SUBSCRIPTIONS_FILENAME",
    "LIFECYCLE_EVENTS_FILENAME",
    "INVOICES_FILENAME",
    "INVOICE_LINES_FILENAME",
    "ACCOUNT_COLUMNS",
    "SUBSCRIBER_COLUMNS",
    "SUBSCRIPTION_COLUMNS",
    "LIFECYCLE_EVENT_COLUMNS",
    "INVOICE_COLUMNS",
    "INVOICE_LINE_COLUMNS",
    "RawEmissionResult",
    "emit_raw_files",
]

ACCOUNTS_FILENAME: str = "accounts.csv"
SUBSCRIBERS_FILENAME: str = "subscribers.csv"
SUBSCRIPTIONS_FILENAME: str = "subscriptions.csv"
LIFECYCLE_EVENTS_FILENAME: str = "lifecycle_events.csv"
INVOICES_FILENAME: str = "invoices.csv"
INVOICE_LINES_FILENAME: str = "invoice_lines.csv"

# Declared grain (constitution rule 15) for the artifacts this slice
# emits.  ``accounts``, ``subscribers``, and ``subscriptions`` are
# now final-simulation-state snapshots, not starter-population
# snapshots; ``lifecycle_events`` is the ordered transition log
# produced by the monthly driver (D40); ``invoices`` and
# ``invoice_lines`` are the ordered billing records the monthly run
# accumulates (D46).
#
# - accounts.csv:         one row per Account in the final
#                         SimulationState.accounts tuple.
# - subscribers.csv:      one row per Subscriber in the final
#                         SimulationState.subscribers tuple.
# - subscriptions.csv:    one row per Subscription in the final
#                         SimulationState.subscriptions tuple
#                         (effective-dated entitlement records).
# - lifecycle_events.csv: one row per emitted lifecycle transition,
#                         month-major and in subscriber order within
#                         each month.
# - invoices.csv:         one row per emitted account-month invoice,
#                         in the simulation result's invoice order
#                         (month-major, then in state account order,
#                         D46).
# - invoice_lines.csv:    one row per emitted recurring-charge invoice
#                         line, in the simulation result's invoice-line
#                         order (D44, D46).
#
# When later slices add payment or hidden-truth artifacts, those get
# their own filenames and grains; the grains above are revisited
# deliberately rather than silently changed.

# Explicit column orders.  These mirror the contract dataclass fields
# exactly (Account, Subscriber, Subscription, LifecycleEvent, Invoice,
# InvoiceLine) and are declared explicitly rather than derived so the
# raw schema is a deliberate, reviewable choice and not an accident of
# field ordering.
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
LIFECYCLE_EVENT_COLUMNS: tuple[str, ...] = (
    "event_id",
    "simulation_month",
    "event_type",
    "account_id",
    "subscriber_id",
    "plan_code",
)
INVOICE_COLUMNS: tuple[str, ...] = (
    "invoice_id",
    "simulation_month",
    "account_id",
    "billing_cycle_day",
    "total_amount",
)
INVOICE_LINE_COLUMNS: tuple[str, ...] = (
    "invoice_line_id",
    "invoice_id",
    "subscriber_id",
    "subscription_id",
    "item_type",
    "item_code",
    "line_amount",
)


# RawEmissionResult is a pure internal return summary.  Every field is
# produced by this module from trusted inputs, so it does not need the
# _Validated vocabulary (D30) — a plain frozen dataclass is enough
# (constitution rule 22).  The fourteen attributes (seven paths + the
# output dir + six record counts) are the natural shape of a batch
# summary; collapsing them into nested sub-objects would obscure the
# result rather than clarify it.
@dataclasses.dataclass(frozen=True)
class RawEmissionResult:  # pylint: disable=too-many-instance-attributes
    """Summary of a single raw-emission batch.

    Attributes:
        output_dir: Directory the batch was written into.
        accounts_path: Path to the emitted ``accounts.csv``.
        subscribers_path: Path to the emitted ``subscribers.csv``.
        subscriptions_path: Path to the emitted ``subscriptions.csv``.
        lifecycle_events_path: Path to the emitted ``lifecycle_events.csv``.
        invoices_path: Path to the emitted ``invoices.csv``.
        invoice_lines_path: Path to the emitted ``invoice_lines.csv``.
        manifest_path: Path to the emitted ``manifest.json``.
        accounts_written: Account rows written (excludes the header).
        subscribers_written: Subscriber rows written.
        subscriptions_written: Subscription rows written.
        lifecycle_events_written: Lifecycle event rows written.
        invoices_written: Invoice rows written.
        invoice_lines_written: Invoice-line rows written.
    """

    output_dir: Path
    accounts_path: Path
    subscribers_path: Path
    subscriptions_path: Path
    lifecycle_events_path: Path
    invoices_path: Path
    invoice_lines_path: Path
    manifest_path: Path
    accounts_written: int
    subscribers_written: int
    subscriptions_written: int
    lifecycle_events_written: int
    invoices_written: int
    invoice_lines_written: int


def emit_raw_files(
    result: SimulationResult,
    output_dir: Path,
) -> RawEmissionResult:
    """Emit raw operational CSV files and a manifest for *result*.

    Creates *output_dir* (and any missing parents) if it does not
    already exist, then writes ``accounts.csv``, ``subscribers.csv``,
    ``subscriptions.csv``, ``lifecycle_events.csv``, ``invoices.csv``,
    ``invoice_lines.csv``, and ``manifest.json``.  Existing files are
    overwritten deterministically.

    The billing files (``invoices.csv``, ``invoice_lines.csv``) are
    serialized straight from ``result.invoices`` and
    ``result.invoice_lines`` in their established order (D46); the
    emitter computes no billing of its own (D47).

    The input *result* is not mutated.

    Args:
        result: The simulation result (final state, ordered lifecycle
            events, and ordered billing records) to serialize.
        output_dir: Directory to write the raw batch into.

    Returns:
        A :class:`RawEmissionResult` summarizing the written batch.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    state = result.state

    # Ordered (filename, columns, records) specs.  The order fixes both
    # the manifest's ``files`` order and the emission sequence; it
    # extends the established four-file order with the two billing files
    # (D47) rather than reordering it.
    file_specs: tuple[tuple[str, tuple[str, ...], Sequence[Any]], ...] = (
        (ACCOUNTS_FILENAME, ACCOUNT_COLUMNS, state.accounts),
        (SUBSCRIBERS_FILENAME, SUBSCRIBER_COLUMNS, state.subscribers),
        (SUBSCRIPTIONS_FILENAME, SUBSCRIPTION_COLUMNS, state.subscriptions),
        (
            LIFECYCLE_EVENTS_FILENAME,
            LIFECYCLE_EVENT_COLUMNS,
            result.lifecycle_events,
        ),
        (INVOICES_FILENAME, INVOICE_COLUMNS, result.invoices),
        (INVOICE_LINES_FILENAME, INVOICE_LINE_COLUMNS, result.invoice_lines),
    )

    written = {
        filename: _write_csv(output_dir / filename, columns, records)
        for filename, columns, records in file_specs
    }

    manifest_path = emit_manifest(
        output_dir,
        tuple((filename, written[filename]) for filename, _, _ in file_specs),
    )

    return RawEmissionResult(
        output_dir=output_dir,
        accounts_path=output_dir / ACCOUNTS_FILENAME,
        subscribers_path=output_dir / SUBSCRIBERS_FILENAME,
        subscriptions_path=output_dir / SUBSCRIPTIONS_FILENAME,
        lifecycle_events_path=output_dir / LIFECYCLE_EVENTS_FILENAME,
        invoices_path=output_dir / INVOICES_FILENAME,
        invoice_lines_path=output_dir / INVOICE_LINES_FILENAME,
        manifest_path=manifest_path,
        accounts_written=written[ACCOUNTS_FILENAME],
        subscribers_written=written[SUBSCRIBERS_FILENAME],
        subscriptions_written=written[SUBSCRIPTIONS_FILENAME],
        lifecycle_events_written=written[LIFECYCLE_EVENTS_FILENAME],
        invoices_written=written[INVOICES_FILENAME],
        invoice_lines_written=written[INVOICE_LINES_FILENAME],
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
