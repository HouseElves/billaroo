# Billaroo

**Generating useful synthetic subscriber billing data.**

**Governed design | Reproducible generation | Analytics-ready**

Billaroo is a clean-room synthetic data generator for subscriber billing scenarios. It is designed to produce tunable, testable billing data that can support downstream analytics, reconciliation, dbt modeling, and data quality experiments without relying on private customer records.

The central claim: **if the truth is known, metric reconstruction can be tested.**

## Current Status

Runnable local pipeline. Billaroo deterministically builds a starter population, advances it through every configured simulation month, applies deterministic subscriber cancellations through explicit ordered semantic action chains, and emits the final account, subscriber, and subscription state alongside an ordered lifecycle-event log as raw operational CSV files plus a JSON manifest. A single `RandomStream` is seeded once and threaded through both stages, so the full set of emitted artifacts is byte-identical for a given `(scenario, seed, code version)`.

Cancellation is the only lifecycle transition currently implemented. The downstream half of the pipeline — billing, payments, hidden truth, PostgreSQL load, dbt models, metric reconciliation — is not yet built.

Implemented today:

- `model/money_model.py` — Decimal money helpers (rule 13)
- `contracts/id_contracts.py` and `contracts/` — deterministic IDs and frozen domain contracts (account, subscriber, subscription, lifecycle event, catalog, and the `Invoice` and `InvoiceLine` invoice records) with structural and semantic validation
- `model/` builders — `build_account`, `build_subscriber`, `build_plan_subscription`, `build_feature_subscription`, `build_catalog`, `build_default_catalog`, and `build_invoice` / `build_invoice_line` for individual records, plus `build_account_month_invoice`, the pure one-account-month operation that selects an active account's chargeable subscriptions, prices each from the catalog, and returns one reconciled invoice and its ordered lines (or `None`)
- `simulate/random_stream.py` — centralized seeded randomness (rule 14)
- `simulate/scenario_config.py` — frozen scenario config with structural validation and coherency-group enforcement (rules 3, 5)
- `simulate/simulation_state.py` + `simulate/population_builder.py` — a deterministic starter-population builder (one account → one subscriber → one plan subscription, optionally one feature subscription, all in month 1)
- `simulate/behavior_model.py` — deterministic cancellation selection: one draw per active subscriber per month, in stable subscriber order, against the month-start state
- `simulate/month_driver.py` — monthly advancement through months 2..N, with month-start intent selection and ordered chain application
- `simulate/simulation_result.py` — frozen, validated record carrying the final `SimulationState` and the ordered `subscriber_cancelled` event log
- `actions/lifecycle_actions.py` + `actions/action_chain.py` + `actions/action_protocols.py` — `CancelSubscriberIntent`, the two-action cancellation chain, and the ordered chain applicator; the `ActionResult` envelope carries lifecycle events plus (empty, for cancellation) invoice and invoice-line tuples, which the chain accumulates in order
- `emit/raw_file_emitter.py` + `emit/manifest_emitter.py` — raw CSV emission for final-state accounts, subscribers, subscriptions, ordered lifecycle events, plus a JSON manifest with declared grain per emitted file (rule 15)
- `synthetic_billing_cli.py` — a thin demo CLI wiring scenario load → catalog → population → monthly simulation → raw emission
- `test/test_file_basename_uniqueness.py` — project-wide guard for rule 18
- `configs/baseline_scenario.yaml` — minimal demo scenario (12 months, 20 starter accounts, `prob_cancel=0.04`)
- `scripts/checkin.sh` and `.github/workflows/checkin.yml` — a local quality-gate script and a CI workflow that runs it

Not yet implemented (and not faked or stubbed elsewhere in the tree):

- monthly lifecycle transitions other than cancellation: upgrades, downgrades, reactivations, feature changes
- billing behaviour beyond the pure model operation and result envelope: the billing semantic action, monthly billing integration, run-level invoice accumulation, and raw invoice/invoice-line file emission (`build_account_month_invoice` can now compute one account-month invoice in the model, and action results can *carry* invoice records, but no action *produces* any and the monthly run does not yet generate or accumulate invoices)
- payments, usage events, adjustments
- a hidden-truth ledger
- the PostgreSQL loader
- dbt models and the metric-reconstruction / reconciliation layer

Most other modules in the tree are intentional zero-length placeholders (see [Design Governance](#design-governance)).

## Contents

- [Current Status](#current-status)
- [What Billaroo Generates](#what-billaroo-generates)
- [Quickstart](#quickstart)
- [Methodology: AI-First Software Engineering](#methodology-ai-first-software-engineering)
- [Design Governance](#design-governance)

## What Billaroo Generates

Billaroo's target output is a full set of telco/sat-radio-style operational records: accounts, subscribers, subscriptions, feature changes, invoices, invoice lines, payments, adjustments, and lifecycle events. These are deliberately shaped to look like raw operational source extracts — pre-bronze CSVs of the kind a real billing system would dump for downstream ingestion.

The intended architecture is a billing analytics flight simulator. The simulator is the trusted source of truth. Alongside the raw operational output it maintains a **hidden truth ledger**. Raw records are loaded into PostgreSQL, a dbt layer reconstructs analytic metrics from those records, and a validation step compares the reconstructed metrics against the hidden truth. That is what makes the central claim testable: *if the truth is known, metric reconstruction can be tested.*

This is not a churn-modeling toy CSV. It is a billing analytics simulator built to send architectural signals: deterministic synthetic data generation, semantic action chains, declared grain on every emitted table, clean separation between simulation and downstream analytics, and known-answer validation.

**Current capability versus planned architecture.** Today Billaroo runs the deterministic cancellation pipeline end to end and emits five total artifacts — four raw operational CSV extracts and one JSON manifest:

```text
build/raw/
    accounts.csv            # one row per Account in the final state
    subscribers.csv         # one row per Subscriber in the final state
    subscriptions.csv       # one row per effective-dated Subscription
    lifecycle_events.csv    # one row per emitted subscriber_cancelled event,
                            # ordered month-major and by subscriber within month
    manifest.json           # one entry per data file with its record count
```

A cancelled subscriber appears in `subscribers.csv` as an inactive row that retains its last assigned `plan_code`; the plan and any feature subscriptions it held appear in `subscriptions.csv` with `end_month` set to the cancellation month and status `ended`. Subscribers active at the end of the run appear as active rows with open-ended subscriptions.

The `Invoice` and `InvoiceLine` record contracts, their `build_invoice` / `build_invoice_line` builders, and the pure model operation `build_account_month_invoice(...)` now exist: given a state, catalog, account, and month, the model can determine which subscriptions are chargeable and build one reconciled account-month invoice with ordered lines. But Billaroo does not yet generate or emit invoices through its runnable simulation path: no billing semantic action exists, the monthly simulation does not generate or accumulate invoices, and no invoice or invoice-line files are emitted. The hidden truth ledger, the rest of the billing and payments capability, the PostgreSQL loader, the dbt reconstruction layer, the validation comparison, and all non-cancellation lifecycle transitions are **planned architecture, not current capability**. The roadmap is recorded honestly in the design log; nothing downstream of raw emission exists in the committed code yet.

## Quickstart

Billaroo uses `pyproject.toml` with an editable install (Python `>=3.11`; a virtual environment is recommended). Install with the development extra and run the test suite:

```bash
pip install -e ".[dev]"
pytest
```

To run a specific test file:

```bash
pytest src/synthetic_billing/simulate/test/test_month_driver.py -v
```

To run the baseline generate-and-simulate demo, which reads `configs/baseline_scenario.yaml`, advances the starter population through months 2..12 with deterministic cancellations, and writes raw files under `build/raw`:

```bash
python -m synthetic_billing.synthetic_billing_cli
```

The defaults can also be passed explicitly; both paths are resolved relative to the current working directory:

```bash
python -m synthetic_billing.synthetic_billing_cli \
    --config configs/baseline_scenario.yaml \
    --output-dir build/raw
```

On success the CLI prints a short deterministic summary and exits `0` (and exits `2` if the configured scenario file is missing):

```text
Synthetic subscriber billing demo complete.
Output directory: build/raw
Accounts written: 20
Subscribers written: 20
Subscriptions written: 20
Lifecycle events written: 4
Lifecycle events file: build/raw/lifecycle_events.csv
Manifest: build/raw/manifest.json
```

The four lifecycle events are deterministic: the baseline scenario is `seed=42`, `months=12`, `starting_accounts=20`, `prob_cancel=0.04`, and the same `(config, seed, code version)` always produces the same five files, byte-for-byte. The Account and Subscriber tuple lengths do not change during the run — cancellation deactivates a subscriber and ends its subscriptions, but never removes rows.

A single check-in script runs every committed quality gate — compileall, pytest, 100% branch coverage, pylint, and a CLI smoke test against a temporary directory. The smoke step verifies that `lifecycle_events.csv` contains at least one data row and that the manifest's reported count for that file agrees with the CSV row count. The smoke test never dirties `build/raw` or the working tree:

```bash
scripts/checkin.sh
```

The GitHub Actions workflow at `.github/workflows/checkin.yml` runs that same script on every push and pull request, so the local gate and the CI gate are the same gate by construction.

## Methodology: AI-First Software Engineering

This project is developed using an AI-first software engineering methodology. In this methodology, the human engineer does not directly type production code as the primary implementation path. The human role is architectural direction, decision ownership, prompt construction, adversarial review, and final acceptance.

The workflow uses a multi-model pipeline with deliberately separated responsibilities. ChatGPT is used for architectural review, prompt refinement, artifact evaluation, and adversarial critique. Claude is used for code generation against reviewed prompts. A third commercial model is planned as an additional prompt-review gate before implementation prompts are sent to the code-generation model. The governing invariant is that no model evaluates its own output.

The key feature of the method is a set of durable governance artifacts that exist outside any single model context. Each project carries a written design constitution, a numbered design log, and project-wide tests that enforce selected architectural rules at runtime. The constitution establishes architectural constraints before significant business logic is added. Tests and validation checks make parts of the constitution executable. The design log records decisions, rationale, alternatives considered, and conditions for revisit.

The design log also establishes precedent. Earlier decisions inform future decisions, while explicit revisit criteria define how those precedents may evolve. Tests and design log entries work together: tests enforce present decisions, while the design log preserves the reasoning needed to refine them responsibly. This allows the project constitution to remain a living document that grows under informed human control as real implementation pressure and changing requirements affect the project.

Generated code must satisfy the project constitution. Review is separated into at least two concerns: whether the code is functionally correct, and whether it preserves the intended architecture. Constitutional adherence is neither an ad hoc process nor an informal preference. It is a documented and binding review target. When implementation pressure reveals an incomplete decision, the original decision is preserved and a refining decision is added. When generated code violates the constitution, the human architect either rejects the generation or records an explicit design-log amendment that changes the governing rule. The constitution does not bend silently. The history of the design is itself a versioned project artifact.

This methodology has been applied to working systems with non-trivial architectural structure. Public demonstrations include the NYC Cab Experiment Platform, a medallion-style experiment pipeline built on open data engineering technologies under a 61-decision design log with strict data quality gates. The Billaroo synthetic data generator project refines the governance pattern developed during the NYC Cab Experiment and incorporates its practical lessons into a more formalized, repeatable process. Billaroo began with a governing 23-rule design constitution and has grown a 44-decision design log through its early stages.

Billaroo has two goals. The first is to deliver a tunable synthetic subscriber billing data generator. The second is to demonstrate a reliable AI-first methodology that controls AI-generated scope creep. The resulting methods are intended to be portable across project types. The specific technologies may change, but the core pattern remains stable: durable design constraints, explicit decision history, separated model responsibilities, adversarial review, executable validation, and human ownership of architecture and acceptance.

## Design Governance

The full charter and architectural rules live in `docs/`. Start with `docs/project_charter.rst` for the project's purpose and audience, and `docs/design_constitution.rst` for the numbered architectural rules. The numbered design log in `design_log.md` records every decision — rationale, alternatives considered, and conditions for revisit — and is the most accurate guide to what is actually committed at any point. Selected constitution rules are made executable by project-wide tests (for example, the file-basename-uniqueness guard for rule 18).

### Intentional zero-length placeholders

Many `.py` files in the source tree are intentional zero-length placeholders for future work. They:

- reserve the basename under design constitution rule 18, preventing duplicate basenames across directories;
- mark the module as a known open slice;
- make the intended repository layout visible while keeping the scope of the current slice narrow.

When a placeholder is implemented, its tests gain real content. Any committed `NotImplementedError` stub requires a matching stub-assertion test under rule 21, so every open work item is explicit and tested rather than silent.

## License

Billaroo is licensed under the GNU Affero General Public License v3.0 or later.

Copyright © 2026 Andrew Milton

See [LICENSE](LICENSE) for the full license text.
