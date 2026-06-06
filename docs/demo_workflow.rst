Demo Workflow
=============

The v0 demo has four stages.

1. Generate Raw Operational Data
--------------------------------

.. code-block:: bash

    synthetic-billing generate \
        --scenario configs/baseline_scenario.yaml \
        --out build/raw

The generator emits raw monthly CSV files and hidden truth files.

2. Load Raw Data Into PostgreSQL
--------------------------------

.. code-block:: bash

    synthetic-billing-dbt load-postgres \
        --raw build/raw \
        --schema synthetic_billing_raw

The loader creates or replaces raw PostgreSQL tables for the generated files.

3. Run dbt
----------

.. code-block:: bash

    cd dbt/subscriber_billing
    dbt build --target local_postgres

dbt stages raw records, reconstructs lifecycle state, reconciles billing
records, and builds monthly customer metrics.

4. Validate Reconstructed Metrics
---------------------------------

.. code-block:: bash

    synthetic-billing-dbt validate-postgres \
        --truth build/raw \
        --schema synthetic_billing_marts

Validation compares dbt-reconstructed metrics against hidden simulator truth.

The validation step exists to prove that analytic truth was reconstructed from
raw operational records rather than painted onto the final mart.