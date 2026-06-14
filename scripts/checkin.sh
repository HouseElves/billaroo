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

echo "==> check-in sanity passed"
