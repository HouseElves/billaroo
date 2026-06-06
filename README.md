# synthetic_subscriber_billing

A clean-room synthetic data generator for subscriber billing analytics.

## What this is

`synthetic_subscriber_billing` generates deterministic telco/sat-radio-style
operational records — accounts, subscribers, subscriptions, feature changes,
invoices, invoice lines, payments, adjustments, and lifecycle events — and
loads them into PostgreSQL 14 so a dbt layer downstream can reconstruct and
validate customer metrics.

The simulator emits raw pre-bronze CSVs that look like operational source
extracts. Alongside the raw output it maintains a hidden truth ledger. dbt
then reconstructs analytic metrics from the raw records, and a validation
step compares those reconstructed metrics against the hidden truth.

The central claim: **if the truth is known, metric reconstruction can be
tested.**

This is not a churn-modeling toy CSV. It is a billing analytics flight
simulator built to send architectural signals: deterministic synthetic data
generation, semantic action chains, declared grain on every emitted table,
clean separation between simulation and downstream analytics, and
known-answer validation.

The full charter and architectural rules live in `docs/`. Start with
`docs/project_charter.rst` and `docs/design_constitution.rst`.

## Current status

Early skeleton. The repository layout is in place and a small foundation
slice is implemented:

- `model/money_model.py` — Decimal money helpers (rule 13)
- `simulate/random_stream.py` — centralized seeded randomness (rule 14)
- `simulate/scenario_config.py` — frozen scenario config with structural
  validation and coherency-group enforcement (rules 3, 5)
- `test/test_file_basename_uniqueness.py` — project-wide guard for rule 18
- `configs/baseline_scenario.yaml` — minimal demo scenario

Most other modules in the tree are intentional zero-length placeholders
(see below). Accounts, subscribers, invoices, payments, action chains, raw
emission, the PostgreSQL loader, dbt models, and the CLI are not yet
implemented.

## How to run the tests

The project uses `pyproject.toml` with an editable install:

```bash
pip install -e ".[dev]"
pytest
```

To run a specific file:

```bash
pytest src/synthetic_billing/simulate/test/test_scenario_config.py -v
```

## What zero-length files mean

Zero-length `.py` files in the source tree are intentional placeholders for
future work. They reserve the basename (design constitution rule 18) and
mark the module as a known open slice. Each one is committed to make the
intended layout visible while keeping the scope of the current slice
narrow.

When a placeholder is implemented, its tests gain real content and any
`NotImplementedError` stubs get matching stub-assertion tests (rule 21).
