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

echo "==> check-in sanity passed"
