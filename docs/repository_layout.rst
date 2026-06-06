Repository Layout
=================

The project uses one Python wheel with multiple import packages.

The generator package owns simulation and raw emission.
The dbt helper package owns PostgreSQL loading and dbt validation helpers.
The dbt project lives beside the Python source tree.

Proposed Layout
---------------

.. code-block:: text

    synthetic_subscriber_billing/
        README.md
        pyproject.toml

        docs/
            project_charter.rst
            design_constitution.rst
            repository_layout.rst
            action_chain_model.rst
            demo_workflow.rst

        configs/
            baseline_scenario.yaml
            price_increase_scenario.yaml
            billing_defect_scenario.yaml

        src/
            synthetic_billing/
                __init__.py
                synthetic_billing_cli.py

                contracts/
                    __init__.py
                    account_contracts.py
                    subscriber_contracts.py
                    subscription_contracts.py
                    invoice_contracts.py
                    payment_contracts.py
                    event_contracts.py
                    truth_contracts.py

                    test/
                        test_account_contracts.py
                        test_subscriber_contracts.py
                        test_subscription_contracts.py
                        test_invoice_contracts.py
                        test_payment_contracts.py
                        test_event_contracts.py
                        test_truth_contracts.py

                model/
                    __init__.py
                    id_model.py
                    money_model.py
                    catalog_model.py
                    account_model.py
                    subscriber_model.py
                    lifecycle_model.py
                    billing_model.py
                    payment_model.py
                    truth_model.py

                    test/
                        test_id_model.py
                        test_money_model.py
                        test_catalog_model.py
                        test_account_model.py
                        test_subscriber_model.py
                        test_lifecycle_model.py
                        test_billing_model.py
                        test_payment_model.py
                        test_truth_model.py

                actions/
                    __init__.py
                    action_protocols.py
                    action_chain.py
                    lifecycle_actions.py
                    subscription_actions.py
                    billing_actions.py
                    payment_actions.py
                    defect_actions.py
                    truth_actions.py

                    test/
                        test_action_protocols.py
                        test_action_chain.py
                        test_lifecycle_actions.py
                        test_subscription_actions.py
                        test_billing_actions.py
                        test_payment_actions.py
                        test_defect_actions.py
                        test_truth_actions.py

                simulate/
                    __init__.py
                    random_stream.py
                    scenario_config.py
                    population_builder.py
                    behavior_model.py
                    month_driver.py
                    simulation_state.py
                    simulation_result.py

                    test/
                        test_random_stream.py
                        test_scenario_config.py
                        test_population_builder.py
                        test_behavior_model.py
                        test_month_driver.py
                        test_simulation_state.py
                        test_simulation_result.py

                emit/
                    __init__.py
                    raw_file_emitter.py
                    manifest_emitter.py
                    postgres_copy_manifest.py

                    test/
                        test_raw_file_emitter.py
                        test_manifest_emitter.py
                        test_postgres_copy_manifest.py

                validate/
                    __init__.py
                    truth_metric_builder.py
                    reconciliation_checks.py
                    deterministic_checks.py

                    test/
                        test_truth_metric_builder.py
                        test_reconciliation_checks.py
                        test_deterministic_checks.py

            synthetic_billing_dbt/
                __init__.py
                synthetic_billing_dbt_cli.py
                postgres_loader.py
                dbt_command_runner.py
                dbt_result_reader.py
                dbt_validation_checks.py

                test/
                    test_postgres_loader.py
                    test_dbt_command_runner.py
                    test_dbt_result_reader.py
                    test_dbt_validation_checks.py

        dbt/
            subscriber_billing/
                dbt_project.yml
                profiles_example.yml

                seeds/
                    plan_catalog_seed.csv
                    feature_catalog_seed.csv

                models/
                    source_definitions.yml

                    staging/
                        stg_accounts.sql
                        stg_subscribers.sql
                        stg_subscription_events.sql
                        stg_invoice_headers.sql
                        stg_invoice_lines.sql
                        stg_payments.sql

                    intermediate/
                        int_subscriber_month_state.sql
                        int_invoice_reconciliation.sql
                        int_lifecycle_reconstruction.sql
                        int_payment_status.sql

                    marts/
                        mart_monthly_customer_metrics.sql
                        mart_billing_reconciliation.sql

                    tests/
                        assert_invoice_lines_match_headers.sql
                        assert_no_orphan_invoice_lines.sql
                        assert_no_orphan_payments.sql
                        assert_lifecycle_matches_truth.sql
                        assert_gold_metrics_match_truth.sql