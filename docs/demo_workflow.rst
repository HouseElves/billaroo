Demo Workflow
=============

The full v0 demo has four stages.  Stage 1 is implemented and
runnable today; stages 2 through 4 are planned architecture.

1. Generate Raw Operational Data  (implemented)
------------------------------------------------

.. code-block:: bash

    python -m synthetic_billing.synthetic_billing_cli \
        --config configs/baseline_scenario.yaml \
        --output-dir build/raw

The CLI builds the deterministic starter population, advances it
through every configured simulation month, applies deterministic
subscriber cancellations through the ordered semantic action chain,
bills every month (including month 1) against the post-transition
state, and emits seven total artifacts under the output directory —
six raw operational CSV extracts and one JSON manifest:

.. code-block:: text

    accounts.csv          # one row per Account in the final state
    subscribers.csv       # one row per Subscriber in the final state
    subscriptions.csv     # one row per effective-dated Subscription
    lifecycle_events.csv  # ordered subscriber_cancelled events
    invoices.csv          # one row per emitted account-month invoice
    invoice_lines.csv     # one row per emitted recurring-charge line
    manifest.json         # one entry per data file with its record count

A single seeded ``RandomStream`` is threaded through both starter-
population construction and monthly simulation, so the same
``(scenario, seed, code version)`` always produces byte-identical
artifacts; billing consumes no random draws.  The CLI's printed
summary reports the invoice and invoice-line files and their row
counts, and the canonical smoke gate verifies the billing artifacts
exist and are internally coherent (manifest agreement, line-to-invoice
integrity, and exact invoice-total reconciliation).

2. Load Raw Data Into PostgreSQL  (planned)
-------------------------------------------

.. code-block:: bash

    synthetic-billing-dbt load-postgres \
        --raw build/raw \
        --schema synthetic_billing_raw

The loader will create or replace raw PostgreSQL tables for the
generated files.  Not implemented.

3. Run dbt  (planned)
---------------------

.. code-block:: bash

    cd dbt/subscriber_billing
    dbt build --target local_postgres

dbt will stage raw records, reconstruct lifecycle state, reconcile
billing records, and build monthly customer metrics.  Not
implemented.

4. Validate Reconstructed Metrics  (planned)
--------------------------------------------

.. code-block:: bash

    synthetic-billing-dbt validate-postgres \
        --truth build/raw \
        --schema synthetic_billing_marts

Validation will compare dbt-reconstructed metrics against hidden
simulator truth.  The validation step exists to prove that analytic
truth was reconstructed from raw operational records rather than
painted onto the final mart.  Not implemented; the hidden-truth
ledger does not yet exist.
