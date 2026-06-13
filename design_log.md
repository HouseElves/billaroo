# Design Log

This document records architectural decisions for the Synthetic Subscriber
Billing project. Each entry explains the rationale, alternatives considered,
and conditions that may cause the decision to be revisited.

Decisions use stable IDs (`D1`, `D2`, ...) that do not change when new
entries are added or existing ones retired. A new decision takes the next
free number; a retired decision keeps its ID with a `Status` line noting
what superseded it. This keeps cross-references stable across the log's
lifetime.

## Decisions

### D1. Clean-Room Synthetic Billing Project

The project is a clean-room synthetic data generator for telco/sat-radio-style
subscriber billing analytics.

#### Rationale

The project demonstrates domain-shaped data generation, metric reconstruction,
and known-answer validation without exposing real subscriber data.

#### Alternatives Considered

- Use a public churn dataset.
- Port the old Scorecard simulator directly.
- Build only a dbt demo over hand-authored CSV files.

#### Revisit When

A real anonymized calibration sample becomes available and privacy-preserving
distribution fitting enters scope.

### D2. Determinism By Seed, Scenario, And Code Version

A repeated run with the same scenario file and seed must produce identical
raw records, hidden truth, and validation results. Determinism is
parameterized by all three of scenario, seed, and code version: a code change
is allowed (and expected) to change outputs, but only when committed.

#### Rationale

The central claim of the project — that dbt reconstruction can be validated
against hidden truth — requires reproducible generated records and metrics.
Where the project emits ordered text artifacts, byte-for-byte reproducibility
is the preferred local invariant.
Determinism also keeps tests fast and useful: failures point at code, not
at random variance.

#### Alternatives Considered

- Seed-only determinism. Outputs would drift across code versions silently.
- Snapshot-based reproducibility with frozen artifacts per release.
- Statistical reconciliation with tolerances.

#### Revisit When

A planned non-deterministic mode (stress test, fuzz scenario) joins the v0
set. Determinism would then be the default and "stochastic with reported
seed" a labeled non-default.

### D3. Abstractions Must Earn Their Existence

The project starts narrow. New abstractions are introduced only after
repeated pressure makes them necessary. Once introduced, an abstraction is
documented with its motivating cases.

#### Rationale

Prior simulator drafts proved the value of the core ideas, but also showed
that speculative generality can obscure the first useful vertical slice.
Restraint is the architectural signal this project tries to send.

#### Alternatives Considered

- Generic simulation framework first, billing-shaped layer on top.
- Plugin system for action types.
- Strategy-pattern config for everything.

#### Revisit When

A third genuine use case forces a new abstraction, or a missing abstraction
turns out to be the source of repeated bugs.

### D4. One Wheel With Multiple Import Packages

The project uses one Python wheel with `synthetic_billing` for generation
and `synthetic_billing_dbt` for downstream PostgreSQL/dbt helpers.

#### Rationale

This mirrors the NYC Cabs multi-module structure while substituting a dbt
parallel track for the Kafka/event track.

#### Alternatives Considered

- Separate repos.
- Separate wheels.
- Place dbt helpers inside the generator package.

#### Revisit When

The dbt helper package gains independent release cadence or external
consumers.

### D5. Generator Core Has No External Operational Dependencies

The generator core may not import or depend on PostgreSQL, dbt, SQLAlchemy,
pandas, Spark, Kafka, network services, or external APIs. It produces raw
records and files. Other modules load those files into downstream systems.

#### Rationale

Simulation should remain deterministic, local, testable, and free of
external operational dependencies. The forbidden-dependency list matches
design constitution rule 6 exactly so it is auditable.

#### Alternatives Considered

- Have the generator write directly to PostgreSQL.
- Have dbt macros participate in simulation.
- Use pandas or SQLAlchemy as intermediate infrastructure.

#### Revisit When

A production-like integration mode requires direct database emission as an
adapter, not as generator core behavior.

### D6. Pure Contracts: No I/O In Contract Modules

Contract modules (`contracts/*.py`) define schemas, constants, deterministic
identifiers, and validation helpers. They perform no I/O: no file access,
no network, no database, no logging. They do not import PostgreSQL, dbt,
pandas, Spark, or network libraries.

#### Rationale

Contracts are the project's vocabulary. Keeping them pure makes them safely
importable from anywhere — generator core, dbt helpers, tests, validation
tools — without dragging in side effects. Strict subset of D5: where D5
forbids external systems, D6 forbids I/O entirely.

#### Alternatives Considered

- Contracts that also load reference data from CSV.
- Contracts that include I/O helpers for convenience.
- One big shared "domain" module.

#### Revisit When

A contract genuinely needs lookup data (e.g. tax tables) that cannot fit in
code. The data load would move to a separate loader; the contract keeps the
schema.

### D7. Local-First Development Workflow

The default workflow writes under `./build` and targets a locally-installed
PostgreSQL 14. Non-local workflows must pass explicit paths, schemas, and
connection settings — there is no implicit cloud fallback.

#### Rationale

Local-first keeps the development loop fast, lets tests run hermetically,
and forces explicit awareness of any departure from the default.

#### Alternatives Considered

- Dev-against-shared-staging by default.
- Cloud-first with local as a special case.
- Containerized PostgreSQL with auto-provisioning.

#### Revisit When

A multi-developer demo environment needs a shared staging schema, or a CI
matrix wants throwaway databases per build.

### D8. Hidden Truth Is Separate From Raw Operational Output

The simulator may produce hidden truth for validation, but emitted raw
files must look like operational records rather than precomputed analytics.

#### Rationale

The demo's central claim is that dbt reconstructs analytic truth from raw
operational exhaust. Mixing truth into raw output would invalidate the
claim.

#### Alternatives Considered

- Emit final customer metrics directly.
- Put truth columns on raw records.
- Validate only with row counts.

#### Revisit When

A teaching/demo mode intentionally exposes truth fields for explanation,
while the validation mode keeps them separate.

### D9. Declared Grain On Every Emitted Table

Every emitted raw table has an explicitly declared grain, documented near
the emitter and referenced in dbt source definitions. Examples: one account
row per account-month, one invoice line per rated charge or adjustment, one
payment activity row per attempted payment.

#### Rationale

Grain confusion is the single biggest source of reconstruction errors in
analytics. Declaring grain at emission makes downstream joins and
aggregations checkable.

#### Alternatives Considered

- Implicit grain via primary keys.
- Grain documented only in dbt model headers.
- A single wide "events" table for everything.

#### Revisit When

A consolidated event-bus style emission becomes a goal, in which case grain
declarations move into event schemas.

### D10. Semantic Action Chains Are First-Class

Business transitions produce ordered semantic action chains. Actions update
simulation state, emit operational facts, and update hidden truth, but do
not directly create final analytic metrics.

#### Rationale

This preserves business intent and prevents lifecycle behavior from being
smeared across table emitters. A cancellation is a semantic event with
operational consequences; the rows are evidence of the action, not the
action itself.

#### Alternatives Considered

- Generate each output table independently.
- Mutate output rows directly from the behavior model.
- Port the old action-dispatch implementation mechanically.

#### Revisit When

Action chains prove too heavy for v0 behavior, or repeated action families
justify stronger protocols.

### D11. Money Uses Decimal; Float Rejected At The Boundary

All monetary values are Python `Decimal` quantized to cents. The
`build_money` helper accepts `int`, `str`, and `Decimal`; it rejects
`float`, `bool`, NaN, and Infinity at the input boundary.

#### Rationale

Floating-point money is a known correctness hazard. Rejecting `float` at
the boundary keeps the invariant local and testable rather than asking
every arithmetic call site to remember.

#### Alternatives Considered

- Float with explicit rounding in arithmetic.
- Integer cents end-to-end.
- A third-party decimal-money library.

#### Revisit When

A locale with non-decimal subunits enters scope, or performance profiling
shows `Decimal` arithmetic on a hot path.

### D12. Randomness Is Centralized In A Seeded Wrapper

All stochastic decisions flow through `RandomStream`, a thin wrapper over
`random.Random`. Code does not call module-level `random.*` functions, and
does not construct ad-hoc `random.Random` instances.

#### Rationale

Centralization gives one place to swap the RNG, one place to log seeds for
reproducibility, and a `grep`-able audit of where randomness enters the
simulator.

#### Alternatives Considered

- Bare `random.Random` instances passed as parameters.
- Module-level `random.seed` at simulator entry.
- NumPy `default_rng` for vectorized streams.

#### Revisit When

A simulation slice needs vectorized RNG (NumPy) or independent named
substreams for parallel scenarios.

### D13. Configuration Objects Are Frozen Dataclasses

`ScenarioConfig` and other configuration classes are
`@dataclass(frozen=True)`. Filesystem values use `pathlib.Path`. No mutable
default values.

#### Rationale

Immutability prevents accidental mid-run config changes, makes config
hashable for caching keys, and clarifies which code holds authoritative
state.

#### Alternatives Considered

- Pydantic models.
- Plain dicts.
- `attrs` with explicit converters.
- Mutable dataclasses with `__setattr__` traps.

#### Revisit When

A nested config tree, environment-overlay system, or per-environment
defaults makes raw dataclasses awkward.

### D14. Configuration Validation Is Syntax-Only

Config validation checks shape, type, range, and internal consistency. It
does not contact external systems. Validating a PostgreSQL config may
check that the port is an integer; it may not check that the database is
reachable.

#### Rationale

Validation belongs near the data, not near the network. Confusing the two
makes tests slow, makes errors confusing, and ties validation to
environment.

#### Alternatives Considered

- Validate-on-load with full preflight (test DB connection, file
  accessibility).
- Defer validation until first use of each field.
- Layered: structural now, semantic-against-environment at edge.

#### Revisit When

A clear "preflight" stage is wanted before any work starts. Preflight would
live at the CLI edge, distinct from config validation.

### D15. Structural And Semantic Validation Are Separate Concerns

Structural validation enforces universal shape rules: probabilities in
[0, 1], months positive, account ids non-empty. Semantic validation
enforces project contract rules: plan code exists in catalog, feature
attachable to plan, event type valid for schema version. The two live in
different modules and run at different stages.

#### Rationale

Structural rules are stable across the project's lifetime; semantic rules
evolve with the catalog. Separating them lets each change independently
and lets tests target each in isolation.

#### Alternatives Considered

- One mega-validator per object.
- Pydantic validators mixed with semantic checks.
- Semantic checks pushed entirely into dbt tests.

#### Revisit When

The structural/semantic line gets fuzzy — for instance, a rule that
simultaneously references a static range and a catalog state.

### D16. Coherency Groups For Related Optional Scenario Knobs

Optional scenario knobs that only make sense as a set are declared in a
`COHERENCY_GROUPS` table and enforced all-or-nothing. The v0 groups are
`price_increase` (month + amount + cancel_lift) and
`duplicate_invoice_line_defect` (month + probability).

#### Rationale

Partial specification of related knobs is almost always user error.
Failing loud at config construction time is cheaper than diagnosing a
silent partial scenario six months later.

#### Alternatives Considered

- Dependent defaults — set the month, auto-fill the amount.
- Silent permissive partial scenarios.
- Warning-only with the run proceeding.

#### Revisit When

A group of three or more knobs appears where partial specification is
genuinely intended, or when a `coherency_warnings_only` mode is needed for
ad-hoc exploration.

### D17. YAML Is The Scenario Configuration Format

Scenarios are stored as YAML files with a flat mapping of `field: value`
lines matching `ScenarioConfig` field names. `Decimal` values are stored
as quoted strings and parsed through `build_money` at load time.

#### Rationale

YAML is human-friendly for inline comments and short scenarios, ubiquitous
in data-engineering workflows, and well-supported by `pyyaml`.

#### Alternatives Considered

- TOML — clean, no boolean quirks, but less common in this domain.
- JSON — no comments, awkward for human authoring.
- Python config classes — full power, no string round-trip, ties config
  to code.

#### Revisit When

YAML's quirks (1.1 boolean coercion, no comment preservation on write-back,
indentation sensitivity) bite, or a scenario grows to a size that demands
better tooling.

### D18. PostgreSQL 14 Is The Local Database Target

The local integration database target is PostgreSQL 14.

#### Rationale

This matches the development environment and provides a realistic
relational target for dbt reconstruction.

#### Alternatives Considered

- DuckDB.
- SQLite.
- Snowflake.
- No database target in v0.

#### Revisit When

A cloud demo or warehouse-specific dbt feature becomes a goal.

### D19. dbt Is Downstream Analytics, Not Simulation

dbt stages raw records, reconstructs lifecycle and billing metrics, and
validates marts against simulator truth. It does not generate simulated
behavior.

#### Rationale

This keeps simulation and analytic reconstruction distinct.

#### Alternatives Considered

- Use dbt seeds as the simulator.
- Put behavior logic in SQL.
- Skip dbt and validate in Python only.

#### Revisit When

Semantic-layer or dbt-native metric definitions become a phase-two signal.

### D20. Side-Effect-Revealing Function Name Prefixes

Functions use one of a small set of prefixes that signals what they do:
`derive_` (pure derivation), `choose_` (seeded stochastic decision),
`build_` (object construction), `apply_` (semantic action application),
`emit_` (file or record emission), `load_` (database loading), `run_`
(orchestration), `validate_` (fail-loud check), `reconcile_` (compare
independent facts). Helpers and methods without one of these prefixes
should be side-effect-free unless their enclosing type makes the side
effect obvious.

#### Rationale

A reader can predict whether a function has side effects from its name
alone. This is especially useful for review, diff reading, and
LLM-assisted refactoring.

#### Alternatives Considered

- Type-system markers (e.g. a `Pure` decorator).
- Docstring conventions only.
- No convention.

#### Revisit When

A category emerges that doesn't fit the existing prefixes — for instance,
streaming or async behavior introducing `stream_` / `await_`.

### D21. Exceptions, Not Assert, For Runtime Validation

User input, scenario config, and inter-module contract checks raise
explicit exceptions (`TypeError`, `ValueError`, custom subclasses).
`assert` is reserved for invariants the test suite must protect — never
for runtime validation.

#### Rationale

`assert` disappears under `python -O`, which can silently weaken
validation in release-style runs. Explicit exceptions also produce better
error messages and are easier to catch in tests.

#### Alternatives Considered

- `assert` for all validation, accept the `-O` risk.
- Decorator-based contract validation.
- A single `validate_runtime` helper that wraps everything.

#### Revisit When

A performance hot path makes per-call exception cost noticeable, in which
case hot-path checks may move behind a development-mode flag.

### D22. Local Tests Live Beside Code

Tests for `foo.py` live in a local `test/test_foo.py` submodule beside the
code.

#### Rationale

This keeps test ownership visible and prevents ambiguity for both human
and LLM-assisted edits.

#### Alternatives Considered

- Central top-level `tests/`.
- Test files without the `test_` prefix.
- Mirror package paths under a single test tree.

#### Revisit When

Packaging or pytest discovery becomes painful enough to justify a different
layout.

### D23. Unique File Basenames With Wrapped-Dunder Exception

Every project file basename is unique except conventional Python files
whose stems are wrapped in double underscores (`__init__.py`,
`__main__.py`, `__about__.py`, and so on). Enforced by a project-level
test that scans from the repository root.

#### Rationale

Unique basenames reduce confusion for both human and LLM-assisted edits,
make `grep` and `find` output unambiguous, and make review/edit
instructions safer. The wrapped-dunder predicate respects Python packaging
conventions in a forward-compatible way.

#### Alternatives Considered

- Allow duplicate test names in separate directories.
- Exempt only `__init__.py` explicitly.
- Enforce uniqueness only under `src`.

#### Revisit When

A tool convention, especially dbt, creates unavoidable repeated basenames.

### D24. Zero-Length Files Are Intentional Placeholders

Zero-length source, test, config, and dbt files may appear as placeholders
for planned modules. A placeholder file carries no public API promise
beyond reserving the basename and planned location.

#### Rationale

They reserve project shape and basenames while letting the current slice
stay focused. Contrast with D25: a placeholder is the softest possible
marker (reserved name only); a `NotImplementedError` stub plus matching
test is the harder marker (reserved name, reserved test, runtime
assertion). Choose placeholders when the slice is months away; choose
stubs when implementation is imminent and a contract is already in mind.

#### Alternatives Considered

- Omit future files until implemented.
- Commit `NotImplementedError` stubs everywhere.
- Fill placeholders with speculative docstrings.

#### Revisit When

Placeholders start confusing tools, coverage, packaging, or readers.

### D25. Stub Tests Accompany NotImplementedError Stubs

If a function or module is committed with a `NotImplementedError` stub, a
matching test exists that asserts the stub raises. The stub-and-test pair
marks the not-yet-implemented slice and is replaced together.

#### Rationale

Stub tests prevent silent regressions (the stub disappearing without an
implementation) and make the open-work surface visible in the test report.

#### Alternatives Considered

- TODO comments only.
- `pytest.skip` markers.
- Tracking stubs in a separate issue list.

#### Revisit When

A large refactor temporarily generates many stubs and the test layer
becomes noisy. An `xfail` strategy might apply in that case.

### D26. Project Tree Is Predeclared But Implemented Incrementally

The repository includes the planned package, dbt, config, and documentation
shape before all modules are implemented.

#### Rationale

The project is being developed with LLM assistance. A visible target tree
reduces naming drift, reserves unique basenames, and gives implementation
sessions stable destinations.

#### Alternatives Considered

- Add directories and files only when implemented.
- Keep the tree only in documentation.
- Let each implementation slice create its own structure.

#### Revisit When

The placeholder tree begins confusing packaging, coverage, documentation,
or reviewers.

### D27. 100% Branch Coverage Is A Hard Commit Requirement

Every commit must achieve 100% branch coverage on the project test suite.
Coverage is checked before commit; a commit that drops below 100% is not
accepted.

#### Rationale

Branch coverage as a commit gate (rather than an aspiration) makes the
test suite's role concrete: the suite is the executable contract on each
decision point in the project code. An uncovered branch means an
untested decision point, and "untested decision point" is exactly the
kind of latent defect this project is built to surface.

100% is enforceable; "high coverage" is not. A 95% threshold would invite
per-diff judgement about which 5% is acceptable to skip. A hard 100%
gate is visible in every diff.

#### Alternatives Considered

- Line coverage only — cheaper, but misses uncovered branches that share
  a line with covered ones.
- ≥95% as a soft target — invites drift and per-PR negotiation.
- Mutation testing — stronger signal, much higher cost; revisit when
  100% branch coverage stops catching real defects.
- No coverage gate, rely on review — works at very small scale, fails
  at this scale.

#### Revisit When

- A branch genuinely cannot be exercised in tests (for example a
  defensive `raise` guarding a state the type system already excludes).
  The policy then needs an explicit, documented `pragma: no branch`
  convention rather than silent erosion of the gate.
- Mutation testing or property-based testing replaces branch coverage as
  the primary correctness signal.
- A test slice is dominated by an external dependency whose contract
  cannot be faithfully mocked.

### D28. Deterministic ID Derivation: SHA-256 Truncated To 16 Hex Chars

IDs are derived as the first 16 lowercase hex characters of the SHA-256
digest of the canonical fields joined with `:`. By convention the first
field is an entity-type prefix (e.g. `account`, `subscriber`,
`subscription`, `invoice`) so IDs from different entity families cannot
collide. String fields must be non-blank and must not contain `:`;
integer ordinal fields must be non-negative; `bool` is rejected
explicitly because `isinstance(True, int)` is True in Python.

#### Rationale

Determinism (D2) requires that IDs be a function of their inputs, not
of generation order. SHA-256 ships with the standard library, has no
licensing weight, and 64 bits of digest (16 hex chars) sit well below
the birthday bound for any scenario this simulator will plausibly
run — order of 10^8 distinct IDs per entity type before collision
probability becomes interesting. The `:` separator is plain ASCII,
easy to grep for, and obvious in test failure output. The leading
entity-type prefix is the cheapest possible namespace and keeps the
primitive a single function rather than one per entity.

#### Alternatives Considered

- UUID4 — not deterministic from inputs; would break D2.
- UUIDv5 — deterministic, but ties the project to RFC 4122 namespace
  ceremony for no operational benefit at this scale.
- Full 64-character SHA-256 digest — collision-safer, but harder to
  scan in test output for no real-world gain at our scale.
- Numeric ordinals end-to-end — easy to read, but couple every ID to
  generation order rather than to the inputs that produced it, which
  makes cross-run diffs noisier than they need to be.
- Per-entity deriver functions (`derive_account_id`, ...) in the
  contract module — postponed until the corresponding entity slices
  land, per D3.

#### Revisit When

- A scenario grows large enough that birthday-bound collisions on a
  16-hex space become plausible (rough threshold: ~10^8 distinct IDs
  per entity type).
- A regulator or downstream consumer requires a specific ID format
  (UUID, ULID, snowflake).
- Per-entity deriver helpers accumulate enough repeated structure
  (entity prefix + canonical field list) that a tiny registry earns
  its place over the bare `derive_id` primitive.

### D29. Account And Subscriber Contracts Establish Static Population Vocabulary

The account and subscriber contracts define the *static population
vocabulary* of the simulator: the entities that exist before any action
chain fires, together with their stable structural attributes — IDs,
ordinals, statuses, plan assignments, billing cycle days, region codes.
This vocabulary is deliberately distinct from the *dynamic vocabulary*
(lifecycle events, invoices, payments, action results) that subsequent
slices will introduce.

#### Rationale

Splitting the contract surface by tempo — static once-set fields versus
dynamic event and transaction records — keeps each contract module
narrow.  Static-population objects can rely on closed value sets
(`ACCOUNT_STATUSES`, `Catalog`-validated `plan_code`) and small fixed
ranges (`billing_cycle_day` in 1..28).  Dynamic contracts will need
open sets, version-aware schemas, and references to action chain
results; keeping those concerns on the other side of the contract
surface prevents event-versioning bleed into the population code.

The four-step ordering inside `build_subscriber`
(derive id → construct → semantic-validate against catalog → return)
makes the structural/semantic boundary from design constitution rule 8
visible in code: the contract `__post_init__` enforces the structural
shape, and only a structurally-valid `Subscriber` is then checked
against catalog membership.

#### Pressure Building Toward A Shared Validation Vocabulary

Three contract modules now duplicate small validation helpers:
non-blank-string checks, bool-rejected ordinal checks, type-then-range
checks for small numeric fields.  Per D3 the helpers stay private and
duplicated for now, but the recurrence is real.

The intended future shape is a skinny, vocabulary-only validation
module — check tuples produced by domain code, consumed by a single
`raise_on_violations(...)` entry point.  We are *not* in the business
of building a validation framework; the goal is a shared declarative
vocabulary, not policy.  Until extraction earns its place, contracts
keep their inline helpers.

#### Alternatives Considered

- A single combined `population_contracts.py` — would couple accounts
  and subscribers, contradicting the narrow-module convention and the
  predeclared layout (D23, D26).
- Embedding plan_code catalog validation in
  `subscriber_contracts.__post_init__` — would force the contract to
  depend on `Catalog`, mixing structural and semantic validation
  against D15.
- Extracting validation helpers now to a shared `_validation.py` —
  premature per D3; three call sites is suggestive but not yet
  decisive, and the future shape is known to differ from the current
  ad-hoc helpers.

#### Revisit When

- A fourth contract module needs the same `_validate_non_blank` /
  `_validate_ordinal` helpers, triggering helper extraction per D3.
- Event, invoice, or payment contracts introduce enough additional
  validation patterns that inline checks become harder to scan than a
  declarative check-tuple list would be.  At that point the shared
  validation vocabulary lands as its own design decision.

### D30. Shared Validation Vocabulary Lands Before Subscription Contracts

The project introduces `synthetic_billing/_validation.py` and
`synthetic_billing/exceptions.py` as a narrow shared validation
vocabulary, lifted and renamed from the NYC Cabs reference module.
The vocabulary defines:

- `CheckTuple` and `CheckSpec` type aliases for validation primitives.
- A free function `raise_on_violations(checks, message)` that raises
  `InvalidRequestError` when any check has failed.
- A `_Validated` mix-in providing `create_validated`, `validate`,
  `is_valid`, and `validity_check` on top of a subclass-declared
  `_type_check_specs` tuple and an optional `_structural_checks`
  override.

The exception hierarchy is deliberately shallow:
`SyntheticBillingError` (root) → `ValidationError` →
`InvalidRequestError` (with a `violations` attribute).

#### Rationale

Account, subscriber, and catalog contracts have repeated validation
helper pressure, and subscription contracts will repeat the same
shape again. The project introduces a narrow validation vocabulary
before the next contract slice to prevent drift.

The vocabulary is **vocabulary, not framework** (D29). It produces
check tuples and consumes them at a single raise site. It does not
own domain rules: catalog membership, billing semantics, lifecycle
policy, or any other project-specific decision lives in the calling
module. The mix-in is intentionally tiny; it could be replaced by
explicit calls to `raise_on_violations` without changing project
semantics.

Existing contracts (D29's static population vocabulary, plus the
catalog) are **not** retrofitted in this slice. Each contract's
adoption of `_Validated` is a separate decision made when the
contract is next opened. This keeps the slice small and prevents
the vocabulary itself from quietly becoming load-bearing before its
shape has been exercised by a real second consumer.

#### Module Placement

The two modules live at the top of the `synthetic_billing` import
package rather than under `contracts/` because they are consumed
across multiple subpackages (contracts and model today; actions and
simulate later). The leading underscore on `_validation.py` flags it
as a project-internal module — public to the package, not to library
consumers.

#### Alternatives Considered

- Placing the vocabulary under `contracts/` — would imply it is only
  for contracts, which is false; action and simulate code will use it
  too.
- Retrofitting accounts, subscribers, and catalog contracts in this
  slice — would couple a vocabulary introduction to three concurrent
  refactors, violating "implement the smallest boring thing" and
  blocking review of the vocabulary on its own merits.
- A full validation framework (declarative schema, error
  serialization, structured logging) — explicitly rejected. The
  project is not in the business of validation frameworks. If a
  richer pattern is needed later, that is a new decision, not a
  silent extension of this one.

#### Revisit When

- Two or three concrete contracts have adopted `_Validated` and
  surfaced common patterns that warrant promotion into the vocabulary
  itself (e.g. a shared `non_blank_string_check` helper).
- An invoice, payment, or event contract introduces a new validation
  shape (non-uniform violation payloads, hierarchical validation,
  async/external checks) that the current vocabulary cannot express
  cleanly.
- A downstream consumer (API surface, dbt validation reporter) needs
  a stable serialization of `InvalidRequestError.violations`, at
  which point the violation shape becomes part of the public
  contract.

### D31. Subscription Contract Proves The Shared Validation Vocabulary

The subscription contract is the first domain contract built on the
shared ``_Validated`` mix-in (D30).  A ``Subscription`` is an
effective-dated entitlement linking a subscriber to a catalog item
(plan or feature) for a range of simulation months.

#### What The POC Proves

- ``_type_check_specs`` handles the seven-field constructor type
  checking declaratively, including the ``int | None`` end_month
  pattern (``(int, type(None))`` as the required type with ``bool``
  excluded).
- ``_structural_checks`` collects all value, range, and cross-field
  violations into a single ``InvalidRequestError`` rather than
  failing at the first one.
- ``create_validated`` sequences type checks → construction →
  structural validation cleanly, matching the four-step builder
  pattern (derive → construct → semantic-validate → return) already
  established in the model layer.
- The contract stays pure — no catalog imports, no model imports, no
  I/O — proving that ``_Validated`` does not pull in unwanted
  dependencies.

#### Structural vs. Semantic Boundary

The ``Subscription`` contract validates shape only:

- Non-blank string identifiers and codes.
- ``item_type`` membership in ``SUBSCRIPTION_ITEM_TYPES``.
- ``start_month >= 1``; ``end_month >= start_month`` when present.
- ``subscription_status`` membership in ``SUBSCRIPTION_STATUSES``.
- Active subscriptions must have ``end_month is None``; ended
  subscriptions must have ``end_month is not None``.

Catalog membership (plan_code exists, feature_code exists) and
compatibility (feature is allowed on plan) live in the model
builders ``build_plan_subscription`` and
``build_feature_subscription``, consistent with D15.

#### Retrofit Posture

Existing account, subscriber, and catalog contracts are **not**
retrofitted in this slice.  The retrofit is the next slice, gated on
this POC passing all three project gates (tests, coverage, lint).
This ordering ensures the vocabulary is proven on a real domain
object before being applied retroactively.

#### Revisit When

- The retrofit slice lands and surfaces any ergonomic friction in the
  ``_Validated`` protocol (e.g. verbose ``_structural_checks``
  methods, awkward ``create_validated`` positional-arg ordering).
- A contract needs multi-phase validation (e.g. structural checks
  that depend on type-check results) that the current single-pass
  ``_structural_checks`` cannot express.
- Event or invoice contracts introduce union-typed fields beyond
  ``int | None`` that stress the ``CheckSpec`` format.

### D32. Existing Contracts Adopt Shared Validation Vocabulary

Catalog, account, and subscriber contracts are retrofitted onto the
shared ``_Validated`` mix-in (D30) that the subscription contract
exercised first (D31).  Every domain dataclass now follows the same
shape:

- frozen dataclass subclassing ``_Validated``
- ``_type_check_specs`` for constructor type validation
- ``_structural_checks`` returning a tuple of ``CheckTuple`` values
  for value, range, vocabulary, and cross-field rules
- construction through ``Class.create_validated(...)`` in model
  builders

Behavior changes are limited to the validation surface and to two
small rule tightenings recorded below.  No new contracts, no new
fields, no changes to ID derivation, no changes to the four-step
model-builder pattern.

#### Validation Behavior Changes

- Constructor type errors that previously raised ``TypeError`` from
  ``__post_init__`` now raise ``InvalidRequestError`` with a
  ``violations`` tuple from ``create_validated``.  Structural errors
  that previously raised ``ValueError`` likewise route through
  ``InvalidRequestError``.
- Multiple violations are collected into one error rather than
  failing at the first bad field.

Direct dataclass construction (e.g. ``Account(...)``) still
constructs without running checks; ``validate()`` and ``is_valid()``
are the explicit entry points for direct-construction paths.  Model
builders always go through ``create_validated``.

#### Rule Tightenings

Two prior structural rules were permissive in earlier
slices and have been tightened here:

- ``FeatureDefinition.allowed_plan_codes`` must be non-empty.  A
  feature with no compatible plans was structurally valid before and
  is rejected now.
- ``Catalog.plans`` must contain at least one plan.  An empty catalog
  was structurally valid before and is rejected now.

Both rules reflect domain truth: a feature with no host plan cannot
be attached, and a catalog with no plans cannot back a scenario.
Either could be relaxed again if a real use case appears.

#### Field Renames

- ``PlanDefinition.plan_name`` → ``PlanDefinition.display_name``
- ``FeatureDefinition.feature_name`` → ``FeatureDefinition.display_name``

Both fields hold the same role — a human-readable label — and were
named asymmetrically only because the original slice handled them in
sequence.  Unifying to ``display_name`` removes a small consistency
burden.

#### Helper And Suppression Removals

The retrofit deletes the per-module ``_validate_non_blank``,
``_validate_ordinal``, ``_validate_non_blank_code``, and
``_validate_decimal_price`` helpers.  Their behavior moves into
``_type_check_specs`` and ``_structural_checks``.  The
``duplicate-code`` (R0801) pylint deduction documented in D29 is
resolved naturally — the duplicated helpers no longer exist.  No new
global pylint suppressions were added; the existing local
suppressions are still justified.

#### Revisit When

- A future contract surfaces a validation pattern that does not fit
  the single-pass ``_structural_checks`` shape (e.g. multi-phase
  validation, externally-supplied checks).
- The tightened rules in this slice (non-empty plans, non-empty
  ``allowed_plan_codes``) need to be relaxed to support a real
  use case.
- A downstream consumer (API surface, dbt reporter, error UX) needs
  a stable serialization of the ``violations`` tuple — at which
  point its shape becomes part of the public contract.

### D33. First Runnable Baseline Produces In-Memory State Only

The first runnable population builder (``build_population``) produces
a deterministic in-memory ``SimulationState`` from a
``ScenarioConfig``, ``Catalog``, and explicit ``RandomStream``.  It
does not emit files, does not implement a CLI, and does not simulate
months beyond the initial population.  Raw CSV emission, CLI
wrapping, and downstream analytics are separate slices.

#### What This Slice Introduces

- ``SimulationState`` — a frozen dataclass using ``_Validated`` (D30)
  with structural checks for element types, ID uniqueness, and
  cross-referential integrity (subscriber → account,
  subscription → subscriber).  Violations are collected per
  constitution rule 23.  Top-level tuple-ness is checked at two
  layers: ``_type_check_specs`` runs at the constructor-validation
  layer (the ``create_validated`` path), and ``_structural_checks``
  re-checks tuple-ness so that direct-construction callers — who
  bypass ``create_validated`` — still get reported as invalid by
  ``validate()`` / ``is_valid()`` rather than silently passing.
  Dependent checks (element types, uniqueness, cross-references) are
  skipped only for the top-level fields that are not safely
  iterable; correctly-typed fields still surface their own
  violations.

- ``build_population`` — creates ``config.starting_accounts``
  accounts, one subscriber per account, one active plan subscription
  per subscriber starting in month 1, and optionally one feature
  subscription per subscriber gated by ``config.prob_feature_add``
  and feature-plan compatibility.  The function takes an explicit
  ``RandomStream`` parameter rather than constructing one internally
  from ``config.seed``; the caller (test, driver, future CLI) is
  responsible for the canonical ``RandomStream(config.seed)``
  pattern.  This keeps the builder decoupled from internal RNG
  construction and makes substream-injection ergonomic when later
  slices need it.

- ``build_default_catalog`` — a convenience helper in
  ``catalog_model.py`` returning a small three-plan, two-feature
  catalog for baseline scenarios and tests.

- Static population vocabulary (regions, billing cycle days) lives in
  ``population_builder.py``, not in contract modules, because it is
  a simulation-level choice.

#### Rationale

Separating in-memory population from file emission keeps each slice
small and testable in isolation.  The population builder proves that
the account → subscriber → subscription construction chain works
end-to-end with deterministic IDs, seeded RNG, and catalog-validated
builders before any I/O concerns enter the picture.

Taking an explicit ``RandomStream`` rather than constructing one
from ``config.seed`` also makes the determinism contract
(D2) testable at the function boundary: identical
``(config, catalog, rng)`` triples produce identical states, and the
test surface does not depend on the builder's internal RNG-creation
choice.

#### Alternatives Considered

- Build population and emit CSVs in one slice — would couple
  construction correctness to file-format concerns.
- Skip ``SimulationState`` and pass loose tuples — would lose the
  structural validation that catches dangling references and
  duplicate IDs at construction time.
- Have ``build_population`` construct its own ``RandomStream`` from
  ``config.seed`` — rejected because it hides RNG construction inside
  the builder and complicates future seed-substream patterns.
- Place default catalog in a config file — premature for v0; a
  code-level helper is simpler and more testable.

#### Revisit When

- The monthly simulation loop extends ``SimulationState`` with
  additional collections (events, invoices, payments, truth records)
  and the dataclass field count warrants a builder or merge pattern.
- A second catalog (e.g. loaded from YAML) makes
  ``build_default_catalog`` redundant for production use.
- The static population vocabulary (regions, billing cycle days)
  needs to become scenario-configurable rather than hardcoded.
- A CLI or driver appears that needs an opinionated convenience
  helper to construct the canonical ``RandomStream(config.seed)``
  pair — at that point the wrapper lives in the driver, not in the
  builder.

### D34. Raw Operational Emission Writes Files Only

The raw emission layer (``emit/raw_file_emitter.py`` and
``emit/manifest_emitter.py``) serializes an already-built in-memory
``SimulationState`` (D33) into raw CSV operational files plus a JSON
manifest under a caller-provided output directory.  This slice writes
records only; it does not run the simulation, compute analytics, or
touch any database.

#### Scope

- Emits ``accounts.csv``, ``subscribers.csv``, ``subscriptions.csv``,
  and ``manifest.json`` from the records that already exist in the
  state.
- Does **not** simulate lifecycle actions, upgrades, cancellations,
  invoices, payments, or usage — none of those records exist yet
  (D33 produced a starter population only).
- Does **not** produce analytic truth, marts, or reconstructed
  business metrics.  Reconstruction is the downstream dbt layer's job
  (D8, D17 era decisions); emission only writes operational exhaust.
- Does **not** load dbt or PostgreSQL, and imports none of the
  forbidden operational dependencies (D5).  Stdlib only: ``csv``,
  ``json``, ``dataclasses``, ``pathlib``.

#### Determinism

Emission is deterministic (D2): stable file names (module constants),
stable column order (explicit ``*_COLUMNS`` tuples mirroring the
contract dataclass fields), stable row order (the order records
appear in the state tuples — no re-sort), stable Unix newlines, and a
stable manifest.  Re-emitting an unchanged state reproduces
byte-identical files.

Serialization is the boring stdlib default: ``csv`` renders ``bool``
(``active``) as ``"True"`` / ``"False"`` and ``None`` (an open
``end_month``) as an empty field.  The raw column schemas are declared
explicitly rather than derived from the dataclasses, so the on-disk
shape is a deliberate, reviewable choice; the header tests restate the
column names literally to catch accidental schema drift.

#### Manifest

``manifest.json`` describes only this raw-emission batch: a
``format_version`` and a ``files`` array of ``name`` /
``record_count`` entries.  It contains **no wall-clock timestamps**.
The project has no deterministic clock abstraction, and a wall-clock
field would break byte-for-byte reproducibility (D2).  A timestamp
field becomes a separate decision once a deterministic clock exists.

#### Declared Grain

Every emitted artifact has a declared grain (constitution rule 15).
These are starter-population snapshots; there is no time dimension yet
because D33 produces only the initial in-memory state.

- ``accounts.csv``: one row per ``Account`` in
  ``SimulationState.accounts`` for the emitted starter population
  snapshot.
- ``subscribers.csv``: one row per ``Subscriber`` in
  ``SimulationState.subscribers`` for the emitted starter population
  snapshot.
- ``subscriptions.csv``: one row per ``Subscription`` in
  ``SimulationState.subscriptions`` for the emitted starter population
  snapshot.
- ``manifest.json``: one manifest document per raw emission batch;
  within the ``files`` array, one entry per emitted raw data file.

When later slices add a month dimension and lifecycle records, these
grains are revisited (e.g. one account per snapshot month) rather than
silently changed.

#### Overwrite Policy

Existing target files are overwritten deterministically, and the
output directory (with any missing parents) is created on demand.
Overwrite was chosen over fail-if-exists because the implementation is
trivial and rerun determinism (proven by test) makes a rerun safe and
idempotent.

#### RawEmissionResult

``emit_raw_files`` returns a frozen ``RawEmissionResult`` summarizing
the batch (the four written paths, the output directory, and three
row counts).  It is a pure internal return summary whose every field
is produced by trusted emitter code, so it does **not** adopt the
``_Validated`` vocabulary (D30) — a plain frozen dataclass is enough
(constitution rule 22).  Its eight attributes carry a local
``too-many-instance-attributes`` suppression with rationale; the flat
shape is the natural form of a batch summary.

#### Not An MVP Yet

This slice does not wire a runnable end-to-end generator.  There is no
CLI and no orchestration from scenario file to emitted batch; a caller
must build the state and invoke ``emit_raw_files`` directly.  The
runnable MVP (CLI wrapping generate → ``build/raw``) is the next
slice.

#### Revisit When

- A deterministic clock abstraction lands and the manifest should
  record a reproducible emission timestamp.
- Later slices add lifecycle events, invoices, or payments to
  ``SimulationState``, at which point new raw files and manifest
  entries are added here (each with a declared grain per constitution
  rule 15).
- ``RawEmissionResult`` becomes a public boundary read by untrusted
  callers, at which point it adopts ``_Validated``.
- The overwrite policy needs to become fail-if-exists for a
  safety-conscious batch mode.

### D35. Minimal CLI Wires Baseline Population to Raw Emission

``synthetic_billing_cli.py`` adds a thin runnable demo wrapper over the
existing baseline path:

    load_scenario_config -> build_default_catalog
    -> RandomStream(config.seed) -> build_population -> emit_raw_files

This makes the baseline runnable from the command line::

    python -m synthetic_billing.synthetic_billing_cli \
        --config configs/baseline_scenario.yaml \
        --output-dir build/raw

#### Scope

- The CLI **orchestrates existing functions only**.  It does not
  reimplement population building (it calls ``build_population``) or
  raw emission (it calls ``emit_raw_files``).
- It keeps randomness centralized: ``rng = RandomStream(config.seed)``
  (D12), constructed by the CLI and passed explicitly into
  ``build_population`` (the explicit-RNG contract from D33).
- It does **not** simulate lifecycle changes, create invoices /
  payments / usage / account actions, compute analytics, or load dbt /
  PostgreSQL.  None of the forbidden operational dependencies (D5) are
  imported.
- It does **not** introduce an orchestration, plugin, logging, or
  application-service framework.  It is ``argparse`` plus a single
  ``main(argv) -> int``.

#### Shape

- ``main(argv: Sequence[str] | None = None) -> int`` returns ``0`` on
  success and ``2`` when the configured scenario file does not exist
  (caught ``FileNotFoundError``, reported to stderr).  Unrecognized
  arguments raise ``SystemExit`` via argparse in the usual way.
- The module guard is ``if __name__ == "__main__": raise
  SystemExit(main())``, carrying ``# pragma: no cover`` so the import
  path stays at 100% branch coverage without a runpy hack.
- A small human-readable summary (output directory, three written
  counts, manifest path) is printed on success.

#### Default Paths

Defaults are intentionally boring and interpreted **relative to the
current working directory**, not as package resources:

- ``--config``: ``configs/baseline_scenario.yaml``
- ``--output-dir``: ``build/raw``

This keeps local demo use simple and avoids package-resource path
complexity for this thin slice.  Tests prove the cwd-relative behavior
by ``monkeypatch.chdir(tmp_path)`` rather than writing into the real
repo tree.

#### Not Full MVP

This slice makes the *baseline starter-population* path runnable.  It
is not the full simulator: there is still no monthly simulation, no
lifecycle events, no invoices or payments, and no downstream dbt /
PostgreSQL reconstruction or validation.  Those remain future work and
this entry makes no MVP-completion claim beyond the baseline
generate -> raw-emit demo.

#### Revisit When

- A monthly simulation loop exists and the CLI needs a verb/subcommand
  surface (at which point a deliberate subcommand decision is made,
  not an ad-hoc accretion of flags).
- Config resolution needs to become package-resource aware rather than
  cwd-relative.
- Downstream loading/validation becomes runnable and the demo workflow
  spans more than generate -> raw-emit.

### D36. README, Local Check-In Gate, and GitHub Quality Gate

This slice puts a public face on the project. It updates the README to
honestly reflect the current local-MVP scope and adds a single check-in
script that the CI workflow defers to, so the gate developers run
locally is the gate CI runs — by construction.

#### What This Slice Adds

- **`README.md`** — rewritten end-to-end as the project's public
  face. It christens the project as **Billaroo**; states the central
  claim that known truth makes metric reconstruction testable; and
  honestly distinguishes current capability from planned architecture.
  It documents the current runnable baseline — deterministic starter
  population, raw CSV emission, manifest emission, and the demo CLI —
  and covers editable install, the test commands, the CLI quickstart
  (with and without explicit arguments), and the local/CI check-in
  gate. The AI-first methodology section is placed before design
  governance. It points to the charter (``docs/project_charter.rst``),
  the design constitution (``docs/design_constitution.rst``), and the
  design log (``design_log.md``), and preserves the explanation of the
  intentional zero-length placeholder files (rules 18 and 21).

- **`scripts/checkin.sh`** — a bash script under ``set -euo
  pipefail`` that ``cd``s to the repo root regardless of where it's
  invoked, then runs ``compileall``, ``pytest``, ``coverage run
  --branch`` + ``coverage report --fail-under=100``, ``pylint``, and a
  CLI smoke test.  The smoke test writes into a ``mktemp -d``
  directory with an ``EXIT`` trap for cleanup, so the working tree is
  never dirtied (``build/raw`` is not touched).  Sections are labelled
  with ``==>`` markers for readable output.

- **`.github/workflows/checkin.yml`** — one Ubuntu job triggered on
  ``push`` and ``pull_request`` with ``permissions: contents: read``.
  Uses ``actions/checkout@v6`` and ``actions/setup-python@v6`` with
  Python ``3.11`` (matching ``pyproject.toml``) and pip caching.  The
  final step runs ``scripts/checkin.sh`` — no gate commands are
  duplicated in YAML, because duplicated gates rot.

#### Honesty Boundaries Enforced

The previous README described planned downstream behavior in a way
that could be read as current project capability. The new README
plainly separates what is built (deterministic starter population +
raw emission + CLI) from what is future work (everything downstream of
raw emission). Future capabilities appear only where they are
explicitly framed as planned architecture or roadmap.

#### What This Slice Does Not Add

No product behavior was changed. No new runtime or dev dependency was
introduced. The slice does not add Docker, tox, nox, pre-commit, a
Makefile, release automation, package publishing, coverage-service
integration, badges, GitHub workflow matrices, or artifact uploads.
It is one README, one shell script, and one workflow.

#### Revisit When

- The default branch name or workflow filename is final and stable —
  at that point a CI status badge in the README earns its place.
- The project grows additional runnable entry points (loader,
  validator) that warrant their own smoke tests inside
  ``scripts/checkin.sh``.
- Python support widens beyond ``3.11`` and the CI workflow grows a
  small version matrix.
- A separate fast-feedback developer script (lint-only, test-only)
  emerges from real workflow pressure (constitution rule 22).

### D37. Project License: AGPL-3.0-or-later

Billaroo is licensed under the GNU Affero General Public License,
version 3.0 or later (``AGPL-3.0-or-later``).

#### What This Slice Adds

- A root-level ``LICENSE`` file containing the full verbatim FSF AGPL
  v3.0 text.
- A ``## License`` section in the README, after Design Governance,
  naming the license, the copyright holder (© 2026 Andrew Milton), and
  pointing to ``LICENSE``.
- A consistent license declaration in ``pyproject.toml`` using the
  PEP 639 SPDX expression ``license = "AGPL-3.0-or-later"`` plus
  ``license-files = ["LICENSE"]``.

#### Rationale

AGPL-3.0 is a deliberate choice for a project whose intended downstream
form is a network-facing analytics pipeline. The AGPL's network-use
clause (section 13, Remote Network Interaction) extends copyleft to
users who interact with a modified version over a network, not only to
those who receive a distributed binary. For a synthetic-data generator
meant to demonstrate governed, reproducible engineering in the open,
the strong-copyleft, source-must-stay-open posture matches the project
intent.

The SPDX string form is used rather than the legacy ``license = {text
= ...}`` table or ``License ::`` trove classifiers because PEP 639 is
the current standard and the two styles must not be mixed. The
``[build-system]`` requirement is raised to ``setuptools>=77.0``, the
first release that understands the PEP 639 ``License-Expression``
metadata, so the declaration is valid against the backend that builds
the wheel. A build was run to confirm the generated metadata carries
``License-Expression: AGPL-3.0-or-later`` and bundles ``LICENSE`` under
``dist-info/licenses/``.

#### Notes

- No per-file copyright/license headers were added. The project does
  not follow a per-file-header convention, and adding noisy headers to
  every module would be out of keeping (constitution rule 22 —
  abstractions, and conventions, earn their existence).
- The license text is the unmodified FSF original; the "How to Apply"
  appendix retains the canonical ``<year>`` / ``<name of author>``
  placeholders, which are part of the license text itself and are not
  meant to be filled in within ``LICENSE``.

#### Revisit When

- The copyright holder set changes (additional contributors,
  assignment to an entity).
- A dual-licensing or relicensing need arises — at which point the
  decision is amended here rather than changed silently.

### D38. First Cancellation Feature Boundary and Dynamic Vocabulary

The first lifecycle-feature slice fixes only the boundary needed to
express deterministic monthly subscriber cancellation:

```
deterministic monthly subscriber cancellation
    -> explicit semantic action chain
    -> lifecycle event emission
```

This decision records the contracts, protocol, result record, and
unimplemented entry points introduced by that slice — and the
behaviour deliberately not introduced.

#### What This Slice Adds

- A lifecycle event vocabulary in
  ``contracts/event_contracts.py``: the constant
  ``SUBSCRIBER_CANCELLED_EVENT_TYPE = "subscriber_cancelled"``, the
  vocabulary tuple ``LIFECYCLE_EVENT_TYPES = (...,)``, and the frozen
  ``LifecycleEvent`` record with structural validation under the
  ``_Validated`` mix-in (D30, D31, constitution rule 23).
- A cancellation intent in
  ``actions/lifecycle_actions.py``: the frozen
  ``CancelSubscriberIntent`` record carrying only ``simulation_month``
  and ``subscriber_id``, plus the unimplemented entry point
  ``build_cancel_subscriber_action_chain``.
- A minimum action protocol and ordered-chain result in
  ``actions/action_protocols.py``: a structural, non-runtime-checkable
  ``SemanticAction`` ``Protocol`` with one method
  ``apply(state) -> ActionResult``, and the frozen ``ActionResult``
  record carrying only the updated ``SimulationState`` and the
  produced ``lifecycle_events`` tuple.
- An unimplemented ordered-chain entry point in
  ``actions/action_chain.py``: ``apply_action_chain(state, actions)``.
- An unimplemented lifecycle event builder in
  ``model/lifecycle_model.py``:
  ``build_subscriber_cancelled_event(state, intent)``.
- Companion tests in each module's local ``test`` submodule that
  exercise the contracts and assert that the three unimplemented
  entry points raise ``NotImplementedError`` immediately
  (constitution rule 21).

#### Boundaries Fixed by This Slice

- Month ``1`` remains the starter-population month; cancellation
  intents and lifecycle events begin at simulation month ``2``.
  Structural validation rejects month ``1`` on both
  ``CancelSubscriberIntent`` and ``LifecycleEvent``.
- ``CancelSubscriberIntent`` carries only month and subscriber
  identity.  Owning account, plan code, and a deterministic event ID
  are resolved from simulation state by later implementation, not
  pre-baked into the intent.
- ``LifecycleEvent`` introduces only the ``subscriber_cancelled``
  event type.  No payload field, source timestamp, prior/new-plan
  field, schema registry, or event-version abstraction is introduced.
- ``ActionResult`` carries only the updated simulation state and the
  ordered ``lifecycle_events`` tuple.  Hidden-truth updates, invoice
  records, payment records, generic record collections, logs,
  warnings, backend handles, success flags, and arbitrary metadata
  are not introduced.
- ``SemanticAction`` is a minimal structural protocol with one method,
  ``apply(state) -> ActionResult``.  It is intentionally not
  runtime-checkable.
- The three public feature entry points
  (``build_cancel_subscriber_action_chain``, ``apply_action_chain``,
  ``build_subscriber_cancelled_event``) are intentionally unimplemented
  stubs in this slice.  Companion tests make the unavailable boundary
  explicit under constitution rule 21.

#### What This Slice Does Not Do

No cancellation state mutation, subscription closing, subscriber
deactivation, action execution, deterministic event-ID derivation,
lifecycle-event construction, monthly iteration, cancellation
probability selection, raw event CSV emission, manifest change, CLI
change, simulation-state coherence change, hidden truth, billing,
PostgreSQL load, or dbt model is implemented here.  Upgrades,
downgrades, reactivation, and later feature changes are also out of
scope.  No generic action registry, plugin architecture, execution
backend, rollback or transaction machinery, or logging/tracing
framework is introduced.

#### Rationale

Carrying the minimum fields on the intent (just month and subscriber)
keeps the contract honest about what the caller actually decided.
Plan code, owning account, and event identity are derived facts; they
belong to the lookup logic that will later resolve them from
simulation state.  Pre-baking them into the intent would predeclare a
derivation that does not exist yet.

The single ``subscriber_cancelled`` event type follows the same logic:
every other event type the project will eventually need (upgrade,
downgrade, reactivation, feature change) requires concrete behaviour
to emit it.  Adding them to the vocabulary now would predeclare
behaviour the project does not own (constitution rule 22).

The ``ActionResult`` shape mirrors the same restraint.  Hidden-truth
updates, invoice records, and payment records are real downstream
concerns, but none of them is reachable from a cancellation chain in
this slice.  When concrete pressure to express them arrives, the
record will be amended here, not amended silently.

#### Revisit When

- Implementation of any of the three stubs reveals that the minimal
  ``CancelSubscriberIntent``, ``LifecycleEvent``, ``ActionResult``,
  or ``SemanticAction`` shape is insufficient — for example, when the
  cancellation chain needs to update hidden truth, emit a billing
  record, or thread an RNG-derived value that cannot be recovered
  from simulation state alone.
- A second lifecycle event type (upgrade, downgrade, reactivation,
  feature change) has concrete construction logic ready to commit, at
  which point ``LIFECYCLE_EVENT_TYPES`` is extended here and the new
  builder is introduced under its own decision.
- A second concrete ``SemanticAction`` implementation arrives and the
  protocol surface needs to widen — at which point the widening is
  decided here, not added silently.
