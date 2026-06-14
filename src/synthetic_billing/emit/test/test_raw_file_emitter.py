"""Tests for raw_file_emitter.py.

Verifies that raw emission writes the expected files with exact, stable
headers; that row order and content mirror a small deterministic
SimulationState; that the manifest record counts match emitted rows;
that reruns are byte-identical (overwrite policy); that an empty state
emits header-only files; that nested output directories are created;
and that the input state is not mutated.
"""

from __future__ import annotations

import csv
import json

from synthetic_billing.contracts.event_contracts import (
    LifecycleEvent,
    SUBSCRIBER_CANCELLED_EVENT_TYPE,
)
from synthetic_billing.emit.manifest_emitter import MANIFEST_FILENAME
from synthetic_billing.emit.raw_file_emitter import (
    ACCOUNTS_FILENAME,
    LIFECYCLE_EVENT_COLUMNS,
    LIFECYCLE_EVENTS_FILENAME,
    SUBSCRIBERS_FILENAME,
    SUBSCRIPTIONS_FILENAME,
    RawEmissionResult,
    emit_raw_files,
)
from synthetic_billing.model.account_model import build_account
from synthetic_billing.model.catalog_model import build_default_catalog
from synthetic_billing.model.subscriber_model import build_subscriber
from synthetic_billing.model.subscription_model import (
    build_feature_subscription,
    build_plan_subscription,
)
from synthetic_billing.simulate.simulation_result import SimulationResult
from synthetic_billing.simulate.simulation_state import SimulationState


# ---- test helpers ----

def _make_small_state() -> SimulationState:
    """Build a deterministic two-account state with one feature sub.

    Subscriber 0 is on STANDARD (CLOUD_DVR compatible) and gets a
    feature subscription; subscriber 1 is on BASIC with only a plan
    subscription.  The feature subscription has ``end_month=None`` so
    the empty-field serialization is exercised.
    """
    catalog = build_default_catalog()
    acct0 = build_account(
        seed=7, account_ordinal=0,
        billing_cycle_day=15, region_code="US-WEST",
    )
    acct1 = build_account(
        seed=7, account_ordinal=1,
        billing_cycle_day=8, region_code="US-EAST",
    )
    sub0 = build_subscriber(acct0.account_id, 0, "STANDARD", catalog)
    sub1 = build_subscriber(acct1.account_id, 0, "BASIC", catalog)
    plan0 = build_plan_subscription(sub0.subscriber_id, "STANDARD", 1, catalog)
    plan1 = build_plan_subscription(sub1.subscriber_id, "BASIC", 1, catalog)
    feat0 = build_feature_subscription(
        sub0.subscriber_id, "CLOUD_DVR", "STANDARD", 1, catalog,
    )
    return SimulationState.create_validated(
        (acct0, acct1),
        (sub0, sub1),
        (plan0, plan1, feat0),
    )


def _make_empty_state() -> SimulationState:
    """Build a structurally valid empty state."""
    return SimulationState.create_validated((), (), ())


def _read_rows(path) -> list[list[str]]:
    """Read a CSV file into a list of string rows (header included)."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def _emit_state(state: SimulationState, output_dir) -> RawEmissionResult:
    """Wrap *state* in a no-events SimulationResult and emit.

    Existing tests pre-date the addition of lifecycle events; they
    assert state-only invariants and ignore the empty event log.
    The lifecycle-event integration is exercised separately in
    :class:`TestRawEmissionLifecycleEvents` below.
    """
    return emit_raw_files(
        SimulationResult.create_validated(state, ()),
        output_dir,
    )


# ---- file creation ----

class TestRawEmissionFiles:
    """Emission creates the expected files."""

    def test_creates_all_files(self, tmp_path) -> None:
        """All four raw files are created in the output directory."""
        _emit_state(_make_small_state(), tmp_path)
        assert (tmp_path / ACCOUNTS_FILENAME).exists()
        assert (tmp_path / SUBSCRIBERS_FILENAME).exists()
        assert (tmp_path / SUBSCRIPTIONS_FILENAME).exists()
        assert (tmp_path / MANIFEST_FILENAME).exists()

    def test_creates_nested_output_dir(self, tmp_path) -> None:
        """A non-existent nested output directory is created."""
        target = tmp_path / "build" / "raw" / "month_0001"
        assert not target.exists()
        _emit_state(_make_small_state(), target)
        assert target.is_dir()
        assert (target / ACCOUNTS_FILENAME).exists()

    def test_result_paths_and_counts(self, tmp_path) -> None:
        """RawEmissionResult reports correct paths and row counts."""
        result = _emit_state(_make_small_state(), tmp_path)
        assert isinstance(result, RawEmissionResult)
        assert result.output_dir == tmp_path
        assert result.accounts_path == tmp_path / ACCOUNTS_FILENAME
        assert result.subscribers_path == tmp_path / SUBSCRIBERS_FILENAME
        assert result.subscriptions_path == tmp_path / SUBSCRIPTIONS_FILENAME
        assert result.manifest_path == tmp_path / MANIFEST_FILENAME
        assert result.accounts_written == 2
        assert result.subscribers_written == 2
        assert result.subscriptions_written == 3


# ---- headers ----

class TestRawEmissionHeaders:
    """CSV headers are exact and stable."""

    def test_accounts_header(self, tmp_path) -> None:
        """accounts.csv header matches the Account contract fields."""
        _emit_state(_make_small_state(), tmp_path)
        rows = _read_rows(tmp_path / ACCOUNTS_FILENAME)
        assert rows[0] == [
            "account_id", "account_ordinal", "billing_cycle_day",
            "region_code", "account_status",
        ]

    def test_subscribers_header(self, tmp_path) -> None:
        """subscribers.csv header matches the Subscriber contract fields."""
        _emit_state(_make_small_state(), tmp_path)
        rows = _read_rows(tmp_path / SUBSCRIBERS_FILENAME)
        assert rows[0] == [
            "subscriber_id", "account_id", "subscriber_ordinal",
            "plan_code", "active",
        ]

    def test_subscriptions_header(self, tmp_path) -> None:
        """subscriptions.csv header matches the Subscription contract fields."""
        _emit_state(_make_small_state(), tmp_path)
        rows = _read_rows(tmp_path / SUBSCRIPTIONS_FILENAME)
        assert rows[0] == [
            "subscription_id", "subscriber_id", "item_type", "item_code",
            "start_month", "end_month", "subscription_status",
        ]


# ---- content ----

class TestRawEmissionContent:
    """Row content and order mirror the input state."""

    def test_account_rows_match_state(self, tmp_path) -> None:
        """accounts.csv data rows mirror the state accounts in order."""
        state = _make_small_state()
        _emit_state(state, tmp_path)
        rows = _read_rows(tmp_path / ACCOUNTS_FILENAME)[1:]
        expected = [
            [
                a.account_id,
                str(a.account_ordinal),
                str(a.billing_cycle_day),
                a.region_code,
                a.account_status,
            ]
            for a in state.accounts
        ]
        assert rows == expected

    def test_subscriber_bool_serialization(self, tmp_path) -> None:
        """The active bool serializes as the stdlib 'True' text."""
        state = _make_small_state()
        _emit_state(state, tmp_path)
        rows = _read_rows(tmp_path / SUBSCRIBERS_FILENAME)[1:]
        # active column is the last column for every subscriber row.
        assert all(row[-1] == "True" for row in rows)

    def test_subscription_rows_match_state(self, tmp_path) -> None:
        """subscriptions.csv data rows mirror the state subscriptions."""
        state = _make_small_state()
        _emit_state(state, tmp_path)
        rows = _read_rows(tmp_path / SUBSCRIPTIONS_FILENAME)[1:]
        expected = [
            [
                s.subscription_id,
                s.subscriber_id,
                s.item_type,
                s.item_code,
                str(s.start_month),
                "" if s.end_month is None else str(s.end_month),
                s.subscription_status,
            ]
            for s in state.subscriptions
        ]
        assert rows == expected

    def test_open_end_month_is_empty_field(self, tmp_path) -> None:
        """A None end_month serializes as an empty CSV field."""
        state = _make_small_state()
        _emit_state(state, tmp_path)
        rows = _read_rows(tmp_path / SUBSCRIPTIONS_FILENAME)[1:]
        # Every subscription in the small state is active (end_month None).
        end_month_index = 5
        assert all(row[end_month_index] == "" for row in rows)

    def test_row_order_is_state_order(self, tmp_path) -> None:
        """Row order follows the state tuple order, not a re-sort."""
        state = _make_small_state()
        _emit_state(state, tmp_path)
        rows = _read_rows(tmp_path / ACCOUNTS_FILENAME)[1:]
        emitted_ids = [row[0] for row in rows]
        assert emitted_ids == [a.account_id for a in state.accounts]


# ---- manifest integration ----

class TestRawEmissionManifest:
    """Manifest counts match emitted rows."""

    def test_manifest_counts_match_rows(self, tmp_path) -> None:
        """Manifest record counts equal the data-row counts per file."""
        _emit_state(_make_small_state(), tmp_path)
        manifest = json.loads(
            (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
        by_name = {
            entry["name"]: entry["record_count"]
            for entry in manifest["files"]
        }
        assert by_name == {
            ACCOUNTS_FILENAME: 2,
            SUBSCRIBERS_FILENAME: 2,
            SUBSCRIPTIONS_FILENAME: 3,
            LIFECYCLE_EVENTS_FILENAME: 0,
        }

    def test_manifest_counts_match_data_rows(self, tmp_path) -> None:
        """Manifest counts equal the actual CSV data-row counts."""
        _emit_state(_make_small_state(), tmp_path)
        manifest = json.loads(
            (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
        by_name = {
            entry["name"]: entry["record_count"]
            for entry in manifest["files"]
        }
        for name, count in by_name.items():
            data_rows = _read_rows(tmp_path / name)[1:]
            assert len(data_rows) == count


# ---- overwrite / determinism ----

class TestRawEmissionRerun:
    """Overwrite policy: reruns are byte-identical."""

    def test_rerun_byte_identical(self, tmp_path) -> None:
        """Re-emitting the same state produces byte-identical files."""
        state = _make_small_state()
        _emit_state(state, tmp_path)
        first = {
            name: (tmp_path / name).read_bytes()
            for name in (
                ACCOUNTS_FILENAME, SUBSCRIBERS_FILENAME,
                SUBSCRIPTIONS_FILENAME, MANIFEST_FILENAME,
            )
        }
        _emit_state(state, tmp_path)
        second = {
            name: (tmp_path / name).read_bytes()
            for name in first
        }
        assert first == second

    def test_overwrite_replaces_stale_file(self, tmp_path) -> None:
        """A pre-existing stale file at a target path is overwritten."""
        (tmp_path / ACCOUNTS_FILENAME).write_text(
            "garbage,data\n1,2\n", encoding="utf-8",
        )
        _emit_state(_make_small_state(), tmp_path)
        rows = _read_rows(tmp_path / ACCOUNTS_FILENAME)
        assert rows[0][0] == "account_id"

    def test_unix_newlines(self, tmp_path) -> None:
        """CSV files use Unix newlines, not CRLF."""
        _emit_state(_make_small_state(), tmp_path)
        raw = (tmp_path / ACCOUNTS_FILENAME).read_bytes()
        assert b"\r\n" not in raw
        assert b"\n" in raw


# ---- empty state ----

class TestRawEmissionEmptyState:
    """An empty but valid state emits header-only files."""

    def test_empty_state_header_only(self, tmp_path) -> None:
        """Each CSV has its header and zero data rows."""
        _emit_state(_make_empty_state(), tmp_path)
        for name in (
            ACCOUNTS_FILENAME, SUBSCRIBERS_FILENAME, SUBSCRIPTIONS_FILENAME,
        ):
            rows = _read_rows(tmp_path / name)
            assert len(rows) == 1  # header only

    def test_empty_state_manifest_zero_counts(self, tmp_path) -> None:
        """The manifest reports zero records for every file."""
        _emit_state(_make_empty_state(), tmp_path)
        manifest = json.loads(
            (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
        assert all(
            entry["record_count"] == 0 for entry in manifest["files"]
        )

    def test_empty_state_result_counts(self, tmp_path) -> None:
        """RawEmissionResult counts are all zero for an empty state."""
        result = _emit_state(_make_empty_state(), tmp_path)
        assert result.accounts_written == 0
        assert result.subscribers_written == 0
        assert result.subscriptions_written == 0


# ---- no mutation ----

class TestRawEmissionNoMutation:
    """Emission does not mutate the input state."""

    def test_state_unchanged(self, tmp_path) -> None:
        """The state tuples are identical objects before and after emit."""
        state = _make_small_state()
        accounts_before = state.accounts
        subscribers_before = state.subscribers
        subscriptions_before = state.subscriptions
        _emit_state(state, tmp_path)
        assert state.accounts is accounts_before
        assert state.subscribers is subscribers_before
        assert state.subscriptions is subscriptions_before

    def test_state_equal_after_emit(self, tmp_path) -> None:
        """The state compares equal to a freshly built identical state."""
        state = _make_small_state()
        _emit_state(state, tmp_path)
        assert state == _make_small_state()


# ---- lifecycle event emission (Slice 3) ----


def _cancellation_event(label: str, month: int = 2) -> LifecycleEvent:
    """Build a labelled subscriber_cancelled lifecycle event."""
    return LifecycleEvent.create_validated(
        f"event-{label}",
        month,
        SUBSCRIBER_CANCELLED_EVENT_TYPE,
        f"acct-{label}",
        f"subscriber-{label}",
        "BASIC",
    )


def _result_with_events(
    *events: LifecycleEvent,
) -> SimulationResult:
    """Build a SimulationResult with the small state and given events."""
    return SimulationResult.create_validated(
        _make_small_state(), tuple(events),
    )


class TestRawEmissionLifecycleEvents:
    """lifecycle_events.csv is written from the simulation result (D40)."""

    def test_lifecycle_events_file_created(self, tmp_path) -> None:
        """The lifecycle events CSV is written even when events are empty."""
        emit_raw_files(_result_with_events(), tmp_path)
        assert (tmp_path / LIFECYCLE_EVENTS_FILENAME).exists()

    def test_empty_events_writes_header_only(self, tmp_path) -> None:
        """An empty event log writes the header row and nothing else."""
        emit_raw_files(_result_with_events(), tmp_path)
        rows = _read_rows(tmp_path / LIFECYCLE_EVENTS_FILENAME)
        assert rows == [list(LIFECYCLE_EVENT_COLUMNS)]

    def test_header_is_lifecycle_event_field_order(self, tmp_path) -> None:
        """The CSV header matches LifecycleEvent field order exactly."""
        emit_raw_files(_result_with_events(), tmp_path)
        rows = _read_rows(tmp_path / LIFECYCLE_EVENTS_FILENAME)
        assert tuple(rows[0]) == LIFECYCLE_EVENT_COLUMNS

    def test_event_rows_match_result_order(self, tmp_path) -> None:
        """Data rows mirror result.lifecycle_events in declared order."""
        events = (
            _cancellation_event("alpha", month=2),
            _cancellation_event("bravo", month=3),
            _cancellation_event("charlie", month=3),
        )
        emit_raw_files(_result_with_events(*events), tmp_path)
        rows = _read_rows(tmp_path / LIFECYCLE_EVENTS_FILENAME)[1:]
        expected = [
            [
                e.event_id,
                str(e.simulation_month),
                e.event_type,
                e.account_id,
                e.subscriber_id,
                e.plan_code,
            ]
            for e in events
        ]
        assert rows == expected

    def test_manifest_includes_lifecycle_events(self, tmp_path) -> None:
        """The manifest entry for lifecycle_events.csv lists its record count."""
        events = (
            _cancellation_event("alpha"),
            _cancellation_event("bravo"),
        )
        emit_raw_files(_result_with_events(*events), tmp_path)
        manifest = json.loads(
            (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
        names_to_counts = {
            entry["name"]: entry["record_count"]
            for entry in manifest["files"]
        }
        assert names_to_counts[LIFECYCLE_EVENTS_FILENAME] == len(events)

    def test_manifest_lists_all_four_data_files(self, tmp_path) -> None:
        """All four data files appear in the manifest in declared order."""
        emit_raw_files(_result_with_events(), tmp_path)
        manifest = json.loads(
            (tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
        names = [entry["name"] for entry in manifest["files"]]
        assert names == [
            ACCOUNTS_FILENAME,
            SUBSCRIBERS_FILENAME,
            SUBSCRIPTIONS_FILENAME,
            LIFECYCLE_EVENTS_FILENAME,
        ]

    def test_result_carries_lifecycle_events_path_and_count(
        self, tmp_path,
    ) -> None:
        """RawEmissionResult exposes the new lifecycle event fields."""
        events = (_cancellation_event("alpha"),)
        result = emit_raw_files(_result_with_events(*events), tmp_path)
        assert result.lifecycle_events_path == (
            tmp_path / LIFECYCLE_EVENTS_FILENAME
        )
        assert result.lifecycle_events_written == 1

    def test_rerun_byte_identical(self, tmp_path) -> None:
        """Two runs with the same result produce a byte-identical CSV."""
        events = (
            _cancellation_event("alpha", month=2),
            _cancellation_event("bravo", month=3),
        )
        emit_raw_files(_result_with_events(*events), tmp_path)
        first = (tmp_path / LIFECYCLE_EVENTS_FILENAME).read_bytes()
        emit_raw_files(_result_with_events(*events), tmp_path)
        second = (tmp_path / LIFECYCLE_EVENTS_FILENAME).read_bytes()
        assert first == second
