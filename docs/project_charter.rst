Project Charter
===============

``synthetic_subscriber_billing`` is a clean-room synthetic data project for
subscriber billing analytics.

The project generates synthetic telco/sat-radio-style operational records:
accounts, subscribers, subscriptions, feature changes, invoices, invoice lines,
payments, adjustments, and lifecycle events.

The generator exists to create controlled raw data for downstream analytics.
It is not a churn-modeling toy CSV.
It is a billing analytics flight simulator.

Purpose
-------

The project demonstrates that realistic subscriber metrics can be reconstructed
from raw operational exhaust.

The simulator generates hidden truth.
The raw outputs deliberately look like operational source extracts.
The dbt layer reconstructs analytic metrics from those raw records.
Validation compares reconstructed dbt metrics against simulator truth.

The central claim is:

    If the truth is known, metric reconstruction can be tested.

Audience
--------

The primary audience is senior data engineering and analytics architecture
reviewers.

The project is intended to send signals in:

- Python package design
- deterministic synthetic data generation
- subscriber billing domain modeling
- PostgreSQL-backed analytics workflows
- dbt staging/intermediate/mart design
- data quality and reconciliation testing
- governed metric reconstruction

Non-Goals
---------

The v0 project is not:

- a production billing simulator
- a privacy-preserving synthetic data product
- a machine-learning churn model
- a Spark project
- a Kafka project
- an Airflow project
- a generalized simulation framework
- a replacement for real anonymized client data

The project may later grow in those directions only when the pressure is real.