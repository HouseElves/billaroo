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

### D39. Cancellation Chain Applies Atomic State Change Then Emits Event

This decision records the product semantics introduced when the
Slice 1 cancellation entry points (D38) are filled in.  Slice 2
implements the three stubs so that one already-selected
``CancelSubscriberIntent`` flows through an ordered semantic action
chain to produce an updated :class:`SimulationState` and exactly one
``subscriber_cancelled`` :class:`LifecycleEvent`.

This slice does not choose cancellations and does not advance
simulation months; those concerns belong to the behaviour model and
month driver, both still unimplemented.

#### Half-Open Subscription Effective Dates

Subscription effective dates for cancellation are interpreted as the
half-open interval ``[start_month, end_month)``.  A subscription
ending in month ``m`` is therefore not active during month ``m``.

Same-month subscription start and cancellation is unsupported:
``[m, m)`` would be an empty effective range and is rejected loudly.
Any active subscription whose ``start_month`` is at least the intent
month is treated as the same defect family and fails the same way.

#### Ordered Two-Action Cancellation Chain

``build_cancel_subscriber_action_chain(intent)`` returns exactly two
ordered semantic actions:

1. **State-change action.** Atomically deactivates the subscriber and
   ends every active plan and feature subscription belonging to that
   subscriber, with ``end_month`` set to the intent month and
   ``subscription_status`` set to ``"ended"``.  Already-ended
   subscriptions and subscriptions belonging to other subscribers are
   preserved exactly.  Tuple order is preserved.  No lifecycle event
   is emitted.
2. **Event-emit action.** Builds the single
   ``subscriber_cancelled`` lifecycle event from the
   post-cancellation state and returns it without modifying state.

Chain order is observable: the event action operates on the state
produced by the state-change action.  The chain returned by the
builder is a frozen tuple and contains exactly these two actions.

#### Atomic Subscriber and Subscription State Change

The state-change action's pre-conditions are checked before any
state is rebuilt:

- the named subscriber must exist;
- the named subscriber must be active;
- the subscriber must own exactly one active plan subscription;
- that plan subscription's ``item_code`` must agree with the
  subscriber's ``plan_code``;
- every active subscription belonging to the subscriber must have
  ``start_month`` strictly less than the intent month.

Any failure raises :class:`InvalidRequestError` with the offending
field captured in ``violations``.  Frozen dataclasses make in-place
mutation physically impossible; record updates are produced through
``dataclasses.replace`` and rebuilt into new tuples, and the new
:class:`SimulationState` is constructed via ``create_validated``,
which revalidates the state-level container, uniqueness, and
cross-reference invariants.

The inactive subscriber's ``plan_code`` is retained.  The retained
plan code is the canonical last-assigned plan, used both for audit
and as the source of the lifecycle event's ``plan_code`` field.

#### Deterministic Cancellation Event Identity

``build_subscriber_cancelled_event(state, intent)`` constructs the
event from the post-cancellation state.  Event-ID derivation follows
the canonical field order required by D38::

    derive_id(
        "lifecycle_event",
        "subscriber_cancelled",
        subscriber_id,
        simulation_month,
    )

The event carries the cancelled subscriber's account ID, subscriber
ID, retained plan code, cancellation month, and the existing
``subscriber_cancelled`` event type.  The builder fails loudly when
the post-state does not unambiguously prove cancellation:

- the subscriber must be present and inactive;
- exactly one plan subscription must have ``end_month`` equal to the
  intent month with status ``"ended"``;
- that plan subscription's ``item_code`` must agree with the
  subscriber's retained ``plan_code``.

#### Ordered Chain Application and Event Accumulation

``apply_action_chain(state, actions)`` runs the chain with these
guarantees:

- every action is invoked exactly once, in tuple order;
- the state passed to each action is the state returned by the
  previous action (state is threaded);
- lifecycle events are accumulated in action order, and within an
  action in emission order;
- an empty action tuple returns the original state and an empty
  event tuple;
- any exception raised by an action propagates unchanged: no retry,
  no wrapping, no rollback, no further actions invoked.

The returned :class:`ActionResult` is constructed through
``create_validated`` so the structural shape of the result is
revalidated at every chain return.

#### Out of Scope for This Slice

This slice does not implement: cancellation probability selection,
monthly iteration, the behaviour model that picks cancellations,
randomness, raw lifecycle-event CSV emission, manifest changes, CLI
changes, upgrade/downgrade/reactivation/feature-change semantics,
account closure, billing, payments, usage, adjustments, hidden truth,
PostgreSQL load, or dbt models.  No generic action registry, plugin
architecture, execution backend, rollback or transaction machinery,
or logging/tracing framework is introduced.

#### Revisit When

- Reactivation arrives and the project needs to distinguish an
  inactive subscriber retaining a plan from one whose plan code
  should be cleared.  At that point the retention rule is amended
  here, not silently changed.
- A second lifecycle action chain (upgrade, downgrade, reactivation,
  feature change) requires more than two ordered actions, or shared
  ordered prelude/postlude steps, at which point the chain shape is
  refined here rather than generalised speculatively.
- Same-month start and cancellation becomes a real scenario — for
  instance, mid-month sign-up immediately followed by cancellation
  with non-empty effective range expressed in days rather than
  months — at which point the effective-date model is refined here.
- An action needs to update hidden truth, emit a billing record, or
  thread an RNG-derived value that cannot be recovered from
  simulation state alone, at which point the
  :class:`ActionResult` shape is amended here under its own
  decision (D38 already records this revisit hook).

### D40. Deterministic Monthly Driver Supports Cancellation Only

Slice 3 wires the cancellation chain into a complete end-to-end path:
the starter population is advanced through simulation months
``2 .. config.months``, deterministically selected cancellations are
applied, and the final state plus ordered lifecycle event log is
emitted alongside the existing raw CSV artifacts.

This decision records the product semantics introduced by that work
— what the monthly driver does, what it deliberately does not do,
and where the boundary sits for later slices.

#### Month-1 Initialisation and Months 2..N Advancement

The starter population produced by ``build_population`` (D33) is the
month-1 state by convention.  The monthly driver advances state
through simulation months ``range(2, config.months + 1)``, which is
empty when ``config.months == 1``.  A one-month scenario therefore
performs no lifecycle transitions and returns a
:class:`SimulationResult` whose ``lifecycle_events`` tuple is empty
and whose ``state`` is the starter state itself.

#### Month-Start Intent Selection

Within a month, the driver snapshots the current threaded state and
calls :func:`behavior_model.choose_cancellation_intents` exactly
once against that snapshot.  All cancellation intents for the month
are chosen from the month-start state before any of them is
applied; within-month state mutations cannot influence selection.

#### Stable Subscriber Ordering and One Draw Per Eligible Subscriber

Selection walks :attr:`SimulationState.subscribers` in stable order
and draws exactly once per subscriber that is active at the start
of the month, regardless of ``prob_cancel``.  The
:class:`RandomStream` position therefore advances by exactly the
active-subscriber count each month, and the resulting event order
is month-major and stable-subscriber-order within each month.

#### No Draws for Inactive Subscribers

A subscriber that is not active at the start of the month is
skipped without drawing.  Subscribers cancelled in an earlier month
remain inactive in every later month and therefore never trigger
another draw or another intent.  A subscriber is consequently
cancelled at most once across the whole run.

#### Cancellation-Only Monthly Scope and Fail-Loud Unsupported Behaviour

This slice supports cancellation as the only monthly transition.
The driver calls :func:`behavior_model.validate_cancellation_only_scope`
before the month loop; any non-zero value for ``prob_upgrade``,
``prob_downgrade``, ``prob_feature_remove``, ``prob_reactivate``,
or ``prob_payment_failure``, and any populated coherency group
(``price_increase`` or ``duplicate_invoice_line_defect``), is
rejected loudly with :class:`InvalidRequestError`.
``prob_feature_add`` is explicitly allowed because it governs
starter-population construction, not monthly transitions.

Rejection happens before any monthly cancellation-selection draws
are consumed, so a rejected configuration never silently advances
the random stream during monthly simulation.  The CLI consumes
starter-population draws via :func:`build_population` before
:func:`run_monthly_simulation` runs this validation, so those
earlier draws are not in the scope of this guarantee.

#### SimulationResult

:class:`SimulationResult` is the result envelope for a full run: a
frozen, validated record carrying the final
:class:`SimulationState` and the ordered ``lifecycle_events``
tuple.  It is distinct from :class:`ActionResult` (the per-action
envelope from Slice 1) — the simulation-level result is the
accumulation of every action-level result the chain produced — and
its structural validation rejects wrong-type fields and bad
elements via the same ``_Validated`` vocabulary as the rest of the
project.

#### Final-State Raw Extracts Plus Ordered Lifecycle-Event Emission

Raw emission was extended to take a :class:`SimulationResult` and
serialise four CSV files plus a manifest:

* ``accounts.csv`` — one row per Account in the final state;
* ``subscribers.csv`` — one row per Subscriber in the final state
  (subscribers cancelled during the run appear as inactive rows
  with their retained ``plan_code``);
* ``subscriptions.csv`` — one row per effective-dated Subscription
  in the final state, including subscriptions that ended during
  the run;
* ``lifecycle_events.csv`` — one row per emitted lifecycle
  transition, with the column order set explicitly from the
  :class:`LifecycleEvent` field order;
* ``manifest.json`` — one document per emission batch, with an
  entry per data file (now including ``lifecycle_events.csv`` and
  its record count).

Row order is the result's tuple order; rerunning emission on the
same :class:`SimulationResult` produces byte-identical files.  The
input result is not mutated.

#### Single Seeded RandomStream for the Whole Run

The CLI constructs one :class:`RandomStream` from ``config.seed``
and threads it through both :func:`build_population` and
:func:`run_monthly_simulation`.  The stream position therefore
evolves deterministically across the run, and the full set of
emitted artifacts is byte-identical for a given ``(config, seed,
code version)``.

#### Deliberately Left for Later Slices

Other monthly transitions (upgrade, downgrade, reactivation,
feature change), account closure, invoices, payments, usage,
adjustments, hidden truth, PostgreSQL load, dbt models, distributed
execution, and generic simulation infrastructure are out of scope
for this slice.  No registry, dispatcher, plugin system,
transaction framework, or scheduler is introduced; the driver is a
plain ordered loop over months that delegates to existing
components.

#### Rationale

The narrow scope is deliberate.  A monthly driver that supports one
transition end-to-end forces the project to wire up the simulation
loop, the raw emission of lifecycle events, the CLI integration,
and the manifest grain — all of which are reused for every
subsequent monthly transition.  Adding a second transition in the
same slice would compound risk without earning new architectural
ground.  The fail-loud rejection of unsupported configuration knobs
makes that scope visible at the boundary, not hidden by a default
of zero.

The single :class:`RandomStream` shared across population
construction and monthly simulation is the simplest pattern that
preserves determinism without forcing the CLI or its callers to
reason about substreams.  When substreams become necessary — for
example, to make starter-population and monthly draws independently
reseedable — the seed-injection point is the CLI, and the change
is recorded as its own decision.

The :class:`SimulationResult` envelope is a distinct type from
:class:`ActionResult` even though they share the same shape: the
simulation-level cumulative result and the action-level
intermediate result are different concepts that happen to factor
into the same fields at the moment.  When implementation pressure
makes them diverge (e.g., the simulation result needs a
hidden-truth section or a run-level summary), the shape is amended
on the appropriate envelope without bleeding into the other.

#### Alternatives Considered

* *Drive monthly simulation from the existing chain runner directly.*
  Rejected: the chain runner operates on a single intent; the
  monthly driver must select intents from a month-start state and
  apply them in order.  Selection is a different responsibility
  that lives at a higher level.
* *Make* :class:`SimulationResult` *an alias for* :class:`ActionResult`.
  Rejected: the two are conceptually distinct (run-level vs
  action-level) even when their fields happen to match, and
  collapsing them now would erase the boundary the moment one of
  them needs to diverge.
* *Treat unsupported probabilities as zero by default and ignore
  them silently.*  Rejected: a non-zero ``prob_upgrade`` in a
  scenario file is a user request that the simulator must either
  honour or refuse.  Silently ignoring it would hide configuration
  bugs and reduce trust in the simulator's outputs.
* *Use a separate seeded stream per stage.*  Rejected for this
  slice: a single stream is sufficient for the cancellation-only
  scope, and substreams would predeclare structure (per-stage
  seeds) that no concrete pressure demands yet.

#### Revisit When

* A second monthly transition (upgrade, downgrade, reactivation,
  feature change) is ready to commit.  At that point the fail-loud
  list shrinks here, ``choose_*`` grows to cover the new
  selection, and the driver's per-month loop is extended.
* Determinism requirements force per-stage RNG streams — for
  example, to keep starter-population draws stable while changing
  monthly behaviour.  At that point the seed-injection point is
  refined here.
* A reactivation transition arrives: it will need to redefine the
  current "no draws for inactive subscribers" rule, and the change
  is recorded here rather than introduced silently.
* The :class:`SimulationResult` shape needs to grow (hidden truth,
  run-level summary, billing summaries) — the new fields are
  decided here rather than added quietly.

### D41. Validated Records Have One Production Construction Boundary

Billaroo's typed records inherit from the ``_Validated`` mix-in
(D30, D31), which provides ``create_validated(...)`` — a classmethod
that runs constructor type checks and then structural validation.
This decision makes the construction convention explicit and adds a
source-level guard that enforces it, without changing any runtime
validation behaviour.

#### The Convention

* Production code builds a ``_Validated`` record through
  ``ClassName.create_validated(...)`` or an established model builder
  (``build_account``, ``build_subscriber``, ``build_plan_subscription``,
  ``build_feature_subscription``, ``build_catalog``,
  ``build_default_catalog``, ``build_subscriber_cancelled_event``).
  Direct dataclass construction (``ClassName(...)``) is not a
  supported production path.
* Direct construction is a test-only escape hatch.  A test that needs
  a deliberately invalid instance — to prove that ``validate()`` or
  ``is_valid()`` rejects it — constructs the dataclass directly,
  bypassing ``create_validated``'s constructor type checks.
* A directly constructed invalid test object is expected to be
  type-correct at the field level: the invalidity it demonstrates
  lives in structural or value rules, not in argument types.  The
  exception is a subclass whose ``_structural_checks`` adds its own
  defensive ``isinstance`` re-checks; those exist so that a
  wrong-typed field is reported as a violation rather than raising
  ``AttributeError`` during iteration, keeping violations safely
  observable under constitution rule 23.
* ``validate()`` is structural-only.  It checks structural and value
  invariants of an already type-correct instance and does not replay
  the constructor type checks declared in ``_type_check_specs``.

#### Enforcement

A project-level test (``test_validated_construction_guard``) scans
non-test production Python source for direct constructor calls to
``_Validated`` subclasses.  It:

* discovers the set of ``_Validated`` subclasses by parsing the source
  tree (no manually duplicated class list), so new validated records
  are covered automatically;
* permits ``ClassName.create_validated(...)`` (an attribute call, not
  a direct constructor call);
* permits direct construction in test source (files named ``test_*``
  or living under a ``test`` package directory);
* reports the offending file, line number, and class name.

The guard parses straightforward source via the standard library
``ast`` module.  It deliberately does not resolve import aliases,
reflection, dynamic imports, ``dataclasses.replace(...)``, or
obscured construction.  It is a small repository hygiene check, not a
general Python name resolver or static-analysis framework.

At the time of this decision the guard finds zero direct-construction
violations in production source: every validated record is already
built through ``create_validated`` or a model builder.  The guard
therefore documents and protects an existing convention rather than
forcing a migration.

#### Rationale

The convention was already followed everywhere in production code,
but it lived only in module docstrings and reviewer attention.  A
source-level guard turns an informal habit into an executable rule
(the same move D18's basename guard and D21's stub-assertion rule
make for their conventions).  Documenting the type-correct
precondition for direct test construction removes a real ambiguity:
without it, a reader cannot tell whether ``validate()`` is expected
to defend against wrong-typed fields, and the answer (structural
checks may, by rule 23, but ``validate()`` does not replay
``_type_check_specs``) needs to be stated once, authoritatively.

Source-level enforcement was chosen over runtime enforcement
because the goal is to keep the production *call sites* honest, not
to change what happens at runtime.  Hiding or wrapping the dataclass
constructor would change runtime behaviour, complicate the
test-only escape hatch, and fight the frozen-dataclass model the
project relies on.

#### Alternatives Considered

* *Add a ``create_invalid()`` constructor for tests.*  Rejected: it
  would bless a second construction path, invite production misuse,
  and duplicate what direct construction already does cleanly in
  tests.
* *Detect tests at runtime (stack inspection, a pytest check, a
  secret token, or a metaclass gate on the constructor).*  Rejected:
  all of these add runtime machinery and fragility to enforce a
  convention that is really about source call sites.  The construction
  boundary is a source property; check it in source.
* *Build a general validation/static-analysis framework or a linter
  plugin.*  Rejected as disproportionate (constitution rule 22).  A
  small ``ast`` walk covering the project's flat
  one-level-from-``_Validated`` inheritance is sufficient and
  reviewable.
* *Make ``validate()`` replay ``_type_check_specs``.*  Rejected: it
  would change runtime behaviour, conflate two distinct layers
  (constructor type checking vs structural validation), and is
  explicitly out of scope.

#### Revisit When

* A validated record needs to inherit from an intermediate validated
  base class rather than directly from ``_Validated``.  The guard's
  discovery is one level deep by base-name match; multi-level
  validated hierarchies would need the discovery widened here.
* A legitimate production construction pattern appears that the guard
  cannot see (for example, deliberate use of
  ``dataclasses.replace(...)`` on a validated record in production).
  At that point the convention and the guard's scope are refined
  here rather than the guard quietly suppressed.
* Direct-construction misuse is found often enough in review that
  runtime enforcement earns its cost — at which point the trade-off
  recorded above is revisited explicitly.

### D42. Invoice And Invoice-Line Record Vocabulary

The first recurring-billing feature round introduces the two smallest
record shapes needed to represent one account's recurring bill for one
simulation month: an ``Invoice`` header and an ``InvoiceLine``.  This
decision establishes their shapes, structural invariants, deterministic
identities, and supported construction path.  It deliberately stops at
the record vocabulary; chargeability, total calculation, the billing
semantic action, driver integration, and raw emission are later
billing slices.

#### The Two Record Shapes

``Invoice`` (in ``contracts/invoice_contracts.py``) has fields, in
order: ``invoice_id: str``, ``simulation_month: int``,
``account_id: str``, ``billing_cycle_day: int``,
``total_amount: Decimal``.

``InvoiceLine`` has fields, in order: ``invoice_line_id: str``,
``invoice_id: str``, ``subscriber_id: str``, ``subscription_id: str``,
``item_type: str``, ``item_code: str``, ``line_amount: Decimal``.

#### Declared Grain (rule 15)

* One ``Invoice`` is one invoice header for one account in one
  simulation month.
* One ``InvoiceLine``, for the currently supported billing vocabulary,
  is one recurring charge for one subscription on one invoice.

The line record is named ``InvoiceLine`` rather than introducing a
separate recurring-charge subtype.  Future taxes, fees, credits,
adjustments, and usage lines are not predeclared.

#### Structural Invariants

``Invoice`` requires a non-blank ``invoice_id`` and ``account_id``; an
integer ``simulation_month`` (``bool`` excluded) of at least ``1``; an
integer ``billing_cycle_day`` (``bool`` excluded) in ``1..28``; and a
``total_amount`` that is a finite ``Decimal``, quantized to cents, and
non-negative.

``InvoiceLine`` requires non-blank ``invoice_line_id``, ``invoice_id``,
``subscriber_id``, ``subscription_id``, and ``item_code``; an
``item_type`` drawn from the existing ``SUBSCRIPTION_ITEM_TYPES``
vocabulary; and a ``line_amount`` that is a finite ``Decimal``,
quantized to cents, and non-negative.

##### Month 1 Is Valid For Invoices

Unlike a ``LifecycleEvent`` (D38), which is restricted to month 2 or
later because month 1 is the starter-population month, an ``Invoice``
may cover month 1.  Billing can occur in the first simulation month, so
the month lower bound is ``1``, not ``2``.  The lifecycle-event month
rule was deliberately not copied.

##### Non-Negative Amounts For The First Recurring-Billing Feature

Both ``total_amount`` and ``line_amount`` must be non-negative.  The
first recurring-billing feature charges for active entitlements; it
emits no credits, refunds, or negative adjustments.  Negative line
families are deferred until the behaviour that produces them exists
(constitution rule 22).

##### Decimal Values Quantized To Cents

Monetary fields are ``Decimal`` values quantized to cents (rule 13).
The contract layer checks the *shape* of an already-built amount —
finite, cents-quantized (exponent no finer than ``-2``), non-negative.
It does not convert raw input into money; conversion happens at the
model-layer ``build_money`` boundary.  The cent precision is duplicated
in ``invoice_contracts.py`` as a local literal rather than imported,
because a pure contract module must not import the model layer; the
value is a fixed property of the money representation, not shared
mutable configuration.

#### Deterministic Identities

``build_invoice`` derives ``derive_id("invoice", account_id,
simulation_month)``.  The ID identifies an account-month invoice;
``billing_cycle_day`` and ``total_amount`` are not identity fields, so
recomputing a month's invoice with a different total does not change
its identity.

``build_invoice_line`` derives ``derive_id("invoice_line", invoice_id,
subscription_id)``.  The current grain permits at most one recurring
charge for a subscription on an invoice, so repeating the same builder
call with the same invoice and subscription yields the same line
identity.  No ordinal, line type, item code, amount, or subscriber id
is folded into the identity in anticipation of future line families.

#### Model Builders Are The Supported D41 Construction Path

``build_invoice`` and ``build_invoice_line`` (in
``model/billing_model.py``) are the supported production construction
path under D41.  Each routes monetary input through ``build_money``
(rejecting ``float``, ``bool``, non-finite, and unsupported input),
derives the deterministic identifier, and constructs the record through
``create_validated(...)``.  Neither performs I/O nor consumes
randomness.  The D41 project guard discovers ``Invoice`` and
``InvoiceLine`` automatically by parsing the source tree; no manual
class list is maintained, and the guard finds zero direct-construction
violations in production source.

#### Excluded Fields

The records deliberately omit invoice status, currency, dates, due
dates, posting periods, line type, line descriptions, quantities, tax
fields, usage fields, adjustment fields, payment fields, arbitrary
payloads, metadata dictionaries, schema registries, and version
abstractions.  Each would be speculative vocabulary without behaviour
to populate it (constitution rule 22).

#### Deferred Cross-Record And Chargeability Concerns

These records do not prove that the referenced account, subscriber, or
subscription exists; that a subscription belongs to its subscriber;
that line item fields agree with the subscription; that a line shares
its invoice's account or month; or that an invoice total equals the sum
of its lines.  They also do not decide which subscriptions are
chargeable.  Those are collection and semantic invariants (rule 8)
owned by later billing slices.

Billaroo still does not generate invoices after this slice: only the
record vocabulary and per-record builders exist.  No semantic action,
driver step, or emitter produces invoices yet.

#### Alternatives Considered

* *Fold ``billing_cycle_day`` or ``total_amount`` into the invoice
  identity.*  Rejected: the account-month is the natural grain, and a
  recomputed total for the same account-month is the same invoice, not
  a new one.
* *Add a line ordinal or line-type to the line identity now.*
  Rejected: the current grain is one recurring charge per subscription
  per invoice, which the (invoice, subscription) pair already
  identifies; an ordinal would anticipate line families that do not
  exist.
* *Introduce a recurring-charge subtype distinct from a general
  invoice line.*  Rejected as premature subtyping; one ``InvoiceLine``
  shape suffices for the only line family that exists.
* *Add a structural money validator or reuse ``build_money`` inside the
  contract.*  Rejected: the contract must stay model-free, and the
  shape check it needs (finite, cents-quantized, non-negative) is a
  small local predicate, not a general validator.
* *Validate account/subscriber/subscription existence in the record.*
  Rejected: that is semantic validation (rule 8) and belongs to the
  billing behaviour that has the surrounding state.

#### Revisit When

* A billing behaviour needs credits, refunds, or negative adjustments,
  at which point the non-negative invariant and possibly a line-type or
  sign field are revisited here.
* Taxes, fees, usage, or proration enter scope and require additional
  line families or fields.
* An invoice must carry currency, dates, status, or a posting period
  for downstream loading or dbt reconstruction.
* More than one recurring charge per subscription per invoice becomes
  possible, at which point the invoice-line identity gains a
  distinguishing field.
* Invoice-to-line reconciliation (total equals sum of lines) is
  implemented as a collection or semantic invariant.

### D43. Action Results Carry Explicit Invoice And Invoice-Line Records

``ActionResult`` (D38) carried only ``state`` and ``lifecycle_events``.
D38 deferred invoice fields until concrete billing pressure appeared.
D42 supplied that pressure by adding the ``Invoice`` and
``InvoiceLine`` records and their builders.  This decision widens the
action-result and ordered-chain contracts so semantic actions may
return those records, and updates the existing cancellation path to the
widened shape.  It does not generate billing records; no action,
driver step, or emitter produces an invoice yet.

#### The Widened Result Shape

``ActionResult`` now has four fields, in this order::

    state: SimulationState
    lifecycle_events: tuple[LifecycleEvent, ...]
    invoices: tuple[Invoice, ...]
    invoice_lines: tuple[InvoiceLine, ...]

The two new tuples are explicit, typed collections — not a generic
emitted-record bag, a record dictionary, an output registry, or a
visitor/dispatcher hook.  Explicit invoice and invoice-line tuples are
the currently justified widening; anything more general would
predeclare capability no concrete action requires (constitution rule
22).

#### Structural Invariants

``ActionResult`` requires ``state`` to be a ``SimulationState`` and
each of ``lifecycle_events``, ``invoices``, and ``invoice_lines`` to be
a tuple containing only instances of its respective element type.
Validation collects all safely observable independent violations
(constitution rule 23): each output collection is checked
independently, so a wrong top-level type on one collection skips only
that collection's per-element checks while the other, well-typed
collections still surface their own per-element violations.  The
top-level field types are re-checked in ``_structural_checks`` so a
directly constructed (test-only) instance still reports its violations
even though it bypasses the constructor type checks (D41).

This boundary adds no cross-record billing reconciliation.  In
particular, ``ActionResult`` does not prove that every invoice line
references an invoice in the same result, that invoice totals equal
line totals, that identities are unique within a result, that records
agree with the state, or that records share an account or month.  Those
require concrete billing behaviour or a broader result boundary and are
deferred.

#### Ordered Accumulation In The Chain

``apply_action_chain`` accumulates lifecycle events, invoices, and
invoice lines independently.  For each collection it preserves action
order and the order produced within each action; it does not
deduplicate, sort, reconcile, or reinterpret records, and records from
one output family never leak into another's collection.  State
threading and exception behaviour are unchanged from D39: each action
is invoked exactly once in tuple order, each receives the state
returned by its predecessor, exceptions propagate unchanged, and no
retry, wrapping, rollback, or further invocation occurs after a
failure.  An empty chain returns the original state object with three
empty output tuples.

#### Cancellation Returns Empty Billing Output

Both cancellation actions (D39) now return the widened result with
empty invoice and invoice-line tuples.  Cancellation is otherwise
unchanged: the chain still has exactly two actions, the state-change
action still emits no lifecycle events, the event action still emits
exactly one ``subscriber_cancelled`` event, and state mutation, event
identity, action order, and exception behaviour remain as accepted in
D39 and D40.  The cancellation intent, event schema, state transition,
driver, probability selection, and raw emission are untouched.

#### ``SemanticAction`` Is Unchanged

The protocol method remains ``apply(state) -> ActionResult``.  Widening
the result record does not require a protocol method or parameter
change, and no billing-specific method is added to ``SemanticAction``.

#### Rationale

D38 deliberately kept ``ActionResult`` minimal and named invoices as a
deferred field pending real pressure.  D42 created the records; a
billing action (a later slice) will need to return them.  Widening the
result now — ahead of the action that populates it — keeps the result
contract and the chain accumulator stable before billing behaviour
lands, so the billing action slice changes only billing logic, not the
shared envelope.  Explicit tuples mirror the existing
``lifecycle_events`` treatment exactly, which keeps the accumulator and
the rule-23 validation uniform across all three output families.

#### Alternatives Considered

* *Defer widening until the billing action exists.*  Rejected: the
  billing-action slice would then have to change the result record, the
  chain accumulator, the cancellation actions, and the billing logic at
  once.  Splitting the envelope change out keeps each slice's diff
  focused and its boundary reviewable.
* *Introduce a generic emitted-record collection or registry.*
  Rejected as premature generalisation (rule 22): only two billing
  record families exist, and explicit tuples are clearer, typed, and
  sufficient.
* *Add billing-specific methods to ``SemanticAction``.*  Rejected: the
  protocol's single ``apply`` method is its whole contract; the widened
  result already carries the new output.
* *Reconcile invoices against lines (or against state) in
  ``ActionResult``.*  Rejected for this slice: reconciliation needs the
  billing behaviour that produces the records and is a semantic concern
  (constitution rule 8), deferred to a later billing slice.

#### Revisit When

* A billing semantic action is introduced and must return invoices and
  invoice lines through this result (the next billing slices).
* Cross-record reconciliation (line-to-invoice references, totals,
  identity uniqueness, state agreement) earns a home — either as
  semantic validation in the producing action or as a broader result
  boundary.
* A third emitted-record family (for example payment activity or hidden
  truth) appears, at which point whether to keep adding explicit tuples
  or to promote a shared abstraction is reconsidered under rule 22.
