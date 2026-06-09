Design Constitution
===================

This document records architectural rules for
``synthetic_subscriber_billing``.

These rules are deliberately restrictive.
The project should demonstrate architectural restraint, not tool accumulation.

1. Deterministic Generation
---------------------------

The generator must be deterministic for a given scenario, seed, and code
version.

A repeated run with the same scenario and seed must produce the same raw data,
the same hidden truth, and the same validation results.

2. Explicit Configuration
-------------------------

Configuration is explicit.

Core code must not perform implicit ``.env`` loading.
Configuration loaders may accept mappings and may fall back to ``os.environ``
only at the edge.

Scenario configuration, database configuration, and dbt execution configuration
are separate concerns.

3. Syntax-Only Configuration Validation
---------------------------------------

Configuration validation checks shape, type, range, and syntax.

Configuration validation does not check external state.

Validating a PostgreSQL config may check that the port is an integer.
It may not check that the database is reachable.

4. Local-First Development
--------------------------

The default local workflow writes under ``./build`` and targets PostgreSQL 14.

Non-local workflows must pass explicit paths, schemas, and connection settings.

5. Immutable Configuration Objects
----------------------------------

Configuration objects are frozen dataclasses.

Filesystem values use ``pathlib.Path``.

6. No External Dependencies in the Generator Core
-------------------------------------------------

The generator core must not depend on:

- PostgreSQL
- dbt
- SQLAlchemy
- pandas
- Spark
- Kafka
- network services
- external APIs

The generator core produces records and files.
Other modules may load those files into downstream systems.

7. Pure Contracts
-----------------

Contract modules define schemas, constants, deterministic identifiers, and
validation helpers.

Contract modules must not perform I/O.
Contract modules must not import PostgreSQL, dbt, pandas, Spark, or network
libraries.

8. Structural and Semantic Validation Are Separate
--------------------------------------------------

Structural validation checks universal shape rules.

Examples:

- probability is between 0 and 1
- month count is positive
- account id is non-empty
- billing cycle day is between 1 and 28

Semantic validation checks project contract rules.

Examples:

- plan code exists in the catalog
- feature code is attachable to a plan
- event type is valid for schema version 1
- scenario name is supported

9. Hidden Truth and Raw Output Are Separate
------------------------------------------

The simulator may maintain hidden truth for validation.

The emitted raw operational records must not contain convenience gold metrics.

The dbt project reconstructs analytic truth from raw operational records.

10. Semantic Actions Are First-Class
------------------------------------

State transitions do not smear updates directly across output tables.

A transition produces one or more semantic actions.
Each action has a business intent.

Examples:

- activate_subscriber
- cancel_subscription
- reactivate_subscriber
- upgrade_plan
- downgrade_plan
- add_feature
- remove_feature
- generate_invoice
- receive_payment
- fail_payment
- apply_adjustment

11. Action Chains Are Explicit and Ordered
------------------------------------------

A business transition may require multiple actions.

Example:

- close_prior_plan_subscription
- open_new_plan_subscription
- emit_upgrade_event
- rate_prorated_charge
- update_hidden_truth

The chain order is part of the model and must be testable.

12. Actions Do Not Manufacture Gold Metrics
-------------------------------------------

Actions may update simulation state.
Actions may emit raw operational records.
Actions may update hidden truth.

Actions must not directly create final analytic metrics.

13. Money Uses Decimal
----------------------

All money arithmetic uses ``Decimal``.

The project must not use ``float`` for money.

14. Randomness Is Centralized
-----------------------------

Randomness flows through a seeded random stream abstraction.

Do not call random functions directly throughout the codebase.

15. Declared Grain
------------------

Every emitted table must have a declared grain.

Examples:

- one account per account snapshot month
- one subscriber per subscriber snapshot month
- one lifecycle event per semantic subscription transition
- one invoice header per account invoice month
- one invoice line per rated charge, credit, tax, fee, or adjustment
- one payment activity record per attempted payment

16. PostgreSQL 14 Is the Local Database Target
----------------------------------------------

The supported local database backend is PostgreSQL 14.

SQL should avoid unnecessary syntax that assumes newer PostgreSQL versions.

17. dbt Is Downstream
---------------------

dbt reconstructs analytics from raw records loaded into PostgreSQL.

dbt must not contain simulation logic.
dbt may compare reconstructed marts to hidden truth only in explicit validation
models or tests.

18. Unique File Basenames
-------------------------

Every file basename in the project must be unique.

Do not create two files named ``model.py`` in different directories.
Do not create two files named ``test_model.py`` in different directories.

Use explicit snake_case names.

19. Local Test Submodules
-------------------------

Tests live in local ``test`` submodules beside the code they exercise.

Tests for ``foo.py`` must live in ``test/test_foo.py``.

20. Side-Effect Naming
----------------------

Function names should reveal side effects.

Use:

- ``derive_*`` for pure deterministic derivation
- ``choose_*`` for seeded stochastic decisions
- ``build_*`` for object construction
- ``apply_*`` for semantic action application
- ``emit_*`` for file or record emission
- ``load_*`` for database loading
- ``run_*`` for orchestration
- ``validate_*`` for fail-loud checks
- ``reconcile_*`` for comparing independent facts

21. Stub Testing
----------------

If a ``NotImplementedError`` stub is committed, it must have a corresponding
test that asserts the stub.

A stub test marks the stub as an explicit open work item.

22. Abstractions Must Earn Their Existence
------------------------------------------

Start small.
Promote abstractions when repeated pressure appears.

Once pressure appears, promote the abstraction decisively and document why.

23. Validation Code Collects All Safely Observable Violations
-------------------------------------------------------------

Validation code should collect all safely observable independent
violations. A failed check should prevent only checks that would be
unsafe or meaningless to evaluate.

For container validation, invalid elements should be reported, then
other checks should continue over the valid typed subset when possible.
For example, a catalog containing one bad plan element should still
report duplicate plan codes among the valid plan elements and unresolved
feature plan references that can be checked safely.

Validation code should not stop at the first failure unless continuing
would require dereferencing invalid structure or would produce misleading
secondary errors.
