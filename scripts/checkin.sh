#!/usr/bin/env bash
# Local check-in quality gate.
#
# Runs every gate the project commits to: compileall, pytest, branch
# coverage at 100%, pylint, and a CLI smoke test against a temporary
# directory.  Mirrored by .github/workflows/checkin.yml so the local
# gate and the CI gate are the same gate by construction (D36).
#
# Safe to invoke from any working directory: the script cd's to the
# repository root first.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "==> compileall"
python -m compileall -q src

echo "==> pytest"
python -m pytest

echo "==> branch coverage (100% required)"
python -m coverage run --branch -m pytest
python -m coverage report --fail-under=100

echo "==> pylint"
python -m pylint src

echo "==> CLI smoke test"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

python -m synthetic_billing.synthetic_billing_cli \
    --config configs/baseline_scenario.yaml \
    --output-dir "${TMP_DIR}/raw"

test -f "${TMP_DIR}/raw/accounts.csv"
test -f "${TMP_DIR}/raw/subscribers.csv"
test -f "${TMP_DIR}/raw/subscriptions.csv"
test -f "${TMP_DIR}/raw/lifecycle_events.csv"
test -f "${TMP_DIR}/raw/invoices.csv"
test -f "${TMP_DIR}/raw/invoice_lines.csv"
test -f "${TMP_DIR}/raw/manifest.json"

# The committed baseline scenario is deterministic and produces at
# least one subscriber_cancelled event.  The smoke test asserts the
# lifecycle_events.csv has a non-empty body, and that the manifest's
# record count for lifecycle_events.csv agrees with the CSV row
# count.  The smoke step never names a specific cancellation count
# (production code must not hard-code one), and any discrepancy fails
# the gate.
python <<PY
import json
import sys
from pathlib import Path

raw_dir = Path("${TMP_DIR}/raw")
events_path = raw_dir / "lifecycle_events.csv"
manifest_path = raw_dir / "manifest.json"

event_lines = events_path.read_text(encoding="utf-8").splitlines()
data_rows = len(event_lines) - 1  # subtract header
if data_rows < 1:
    sys.exit(
        f"lifecycle_events.csv has {data_rows} data row(s); "
        "expected at least 1 from the baseline scenario"
    )

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
counts = {entry["name"]: entry["record_count"] for entry in manifest["files"]}
manifest_event_count = counts.get("lifecycle_events.csv")
if manifest_event_count != data_rows:
    sys.exit(
        f"manifest lifecycle_events.csv count "
        f"{manifest_event_count} != csv data row count {data_rows}"
    )

print(
    f"lifecycle_events.csv: {data_rows} data row(s); manifest agrees"
)
PY

# Billing smoke evidence (D48).  The committed baseline is deterministic
# and bills every active account-month, so it produces at least one
# invoice and one invoice line.  The smoke step proves the emitted
# billing artifacts are present and internally coherent without freezing
# the incidental baseline invoice or line counts: it checks the manifest
# counts agree with the CSV row counts, that every emitted line
# references an emitted invoice, and that each invoice total equals the
# exact Decimal sum of its own lines.  Reconciliation lives here, in the
# gate, not in the CLI or the emitter.
python <<PY
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

raw_dir = Path("${TMP_DIR}/raw")
invoices_path = raw_dir / "invoices.csv"
lines_path = raw_dir / "invoice_lines.csv"
manifest_path = raw_dir / "manifest.json"


def read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


invoices = read_rows(invoices_path)
lines = read_rows(lines_path)

if len(invoices) < 1:
    sys.exit(
        f"invoices.csv has {len(invoices)} data row(s); "
        "expected at least 1 from the baseline scenario"
    )
if len(lines) < 1:
    sys.exit(
        f"invoice_lines.csv has {len(lines)} data row(s); "
        "expected at least 1 from the baseline scenario"
    )

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
counts = {entry["name"]: entry["record_count"] for entry in manifest["files"]}
for name, rows in (("invoices.csv", invoices), ("invoice_lines.csv", lines)):
    if counts.get(name) != len(rows):
        sys.exit(
            f"manifest {name} count {counts.get(name)} "
            f"!= csv data row count {len(rows)}"
        )

invoice_ids = {row["invoice_id"] for row in invoices}
for line in lines:
    if line["invoice_id"] not in invoice_ids:
        sys.exit(
            f"invoice_lines.csv references unknown invoice_id "
            f"{line['invoice_id']!r}"
        )

line_totals = defaultdict(lambda: Decimal("0"))
for line in lines:
    line_totals[line["invoice_id"]] += Decimal(line["line_amount"])
for invoice in invoices:
    invoice_total = Decimal(invoice["total_amount"])
    summed = line_totals[invoice["invoice_id"]]
    if invoice_total != summed:
        sys.exit(
            f"invoice {invoice['invoice_id']!r} total {invoice_total} "
            f"!= sum of its lines {summed}"
        )

print(
    f"invoices.csv: {len(invoices)} invoice(s), "
    f"{len(lines)} line(s); manifest agrees, totals reconcile"
)
PY

echo "==> check-in sanity passed"
