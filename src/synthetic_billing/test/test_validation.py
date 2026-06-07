"""Tests for synthetic_billing._validation."""

import dataclasses

import pytest

from synthetic_billing._validation import (
    _Validated,
    raise_on_violations,
)
from synthetic_billing.exceptions import InvalidRequestError


# ---------------------------------------------------------------------------
# Sample subclasses used to exercise the _Validated mix-in
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _Sample(_Validated):
    """A two-field validated dataclass with one structural rule.

    ``count`` excludes ``bool`` (the canonical int-vs-bool pattern) and
    must be non-negative as a structural check.
    """

    name: str
    count: int

    _type_check_specs = (
        ("name", str),
        ("count", int, bool),
    )

    def _structural_checks(self):
        return ((self.count >= 0, "count", self.count),)


@dataclasses.dataclass(frozen=True)
class _NoStructuralRules(_Validated):
    """A validated dataclass that only does type checks, no structural rules."""

    value: int

    _type_check_specs = (("value", int, bool),)


# ---------------------------------------------------------------------------
# raise_on_violations
# ---------------------------------------------------------------------------


class TestRaiseOnViolations:
    """raise_on_violations only raises when at least one check has failed."""

    def test_empty_checks_no_raise(self) -> None:
        """An empty check sequence is a no-op."""
        raise_on_violations([], "ignored")

    def test_all_passing_no_raise(self) -> None:
        """All-passing checks produce no exception."""
        raise_on_violations(
            [(True, "a", 1), (True, "b", 2)],
            "ignored",
        )

    def test_single_violation_raises(self) -> None:
        """A single failing check raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError) as exc_info:
            raise_on_violations(
                [(False, "field", "bad-value")],
                "boom",
            )
        assert exc_info.value.violations == (("field", "bad-value"),)

    def test_multiple_violations_collected(self) -> None:
        """Only failing checks appear in the violations tuple, in order."""
        with pytest.raises(InvalidRequestError) as exc_info:
            raise_on_violations(
                [
                    (False, "a", 1),
                    (True, "b", 2),
                    (False, "c", 3),
                ],
                "boom",
            )
        assert exc_info.value.violations == (("a", 1), ("c", 3))

    def test_message_propagated(self) -> None:
        """The supplied message becomes the exception's str()."""
        with pytest.raises(InvalidRequestError, match="custom message"):
            raise_on_violations([(False, "f", 0)], "custom message")


# ---------------------------------------------------------------------------
# _Validated.create_validated
# ---------------------------------------------------------------------------


class TestCreateValidatedHappyPath:
    """create_validated builds the instance, runs type checks, then validates."""

    def test_returns_instance(self) -> None:
        """A valid call returns a properly-typed dataclass instance."""
        sample = _Sample.create_validated("foo", 5)
        assert isinstance(sample, _Sample)
        assert sample.name == "foo"
        assert sample.count == 5

    def test_zero_is_valid_count(self) -> None:
        """The structural check accepts the boundary value zero."""
        sample = _Sample.create_validated("foo", 0)
        assert sample.count == 0


class TestCreateValidatedArgCount:
    """create_validated rejects mismatched argument counts up-front."""

    def test_too_few_args(self) -> None:
        """Fewer args than specs raises TypeError."""
        with pytest.raises(TypeError, match="expected 2 arguments"):
            _Sample.create_validated("foo")

    def test_too_many_args(self) -> None:
        """More args than specs raises TypeError."""
        with pytest.raises(TypeError, match="expected 2 arguments"):
            _Sample.create_validated("foo", 5, "extra")

    def test_no_args(self) -> None:
        """Zero args for a non-empty spec raises TypeError."""
        with pytest.raises(TypeError, match="received 0"):
            _Sample.create_validated()


class TestCreateValidatedTypeChecks:
    """create_validated routes constructor-type failures through raise_on_violations."""

    def test_wrong_required_type(self) -> None:
        """A value of the wrong required type is reported as a violation."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _Sample.create_validated(42, 5)
        assert ("name", 42) in exc_info.value.violations

    def test_excluded_type_rejected(self) -> None:
        """A value matching the excluded type is rejected even if int."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _Sample.create_validated("foo", True)
        assert ("count", True) in exc_info.value.violations

    def test_message_names_class(self) -> None:
        """The error message names the class that failed type checking."""
        with pytest.raises(InvalidRequestError, match="_Sample"):
            _Sample.create_validated(42, 5)

    def test_multiple_type_failures_collected(self) -> None:
        """Multiple type failures are accumulated into one error."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _Sample.create_validated(42, True)
        assert ("name", 42) in exc_info.value.violations
        assert ("count", True) in exc_info.value.violations


class TestCreateValidatedStructuralChecks:
    """create_validated runs structural checks after type checks succeed."""

    def test_structural_failure_raises(self) -> None:
        """A negative count fails the >= 0 structural rule."""
        with pytest.raises(InvalidRequestError) as exc_info:
            _Sample.create_validated("foo", -1)
        assert ("count", -1) in exc_info.value.violations

    def test_structural_message_names_class(self) -> None:
        """The structural error message names the failing class."""
        with pytest.raises(InvalidRequestError, match="_Sample"):
            _Sample.create_validated("foo", -1)


# ---------------------------------------------------------------------------
# _Validated.validate / is_valid / validity_check
# ---------------------------------------------------------------------------


class TestValidate:
    """validate() raises only when a structural check has failed."""

    def test_passes_silently(self) -> None:
        """A valid instance's validate() returns None."""
        sample = _Sample(name="foo", count=5)
        assert sample.validate() is None

    def test_fails_loudly(self) -> None:
        """An invalid instance's validate() raises InvalidRequestError."""
        sample = _Sample(name="foo", count=-1)
        with pytest.raises(InvalidRequestError):
            sample.validate()

    def test_default_structural_checks_pass(self) -> None:
        """A subclass that does not override _structural_checks validates trivially."""
        instance = _NoStructuralRules(value=5)
        assert instance.validate() is None


class TestIsValid:
    """is_valid() returns True/False without leaking exceptions."""

    def test_true_for_valid(self) -> None:
        """A valid instance returns True."""
        sample = _Sample(name="foo", count=5)
        assert sample.is_valid() is True

    def test_false_for_invalid(self) -> None:
        """An invalid instance returns False instead of raising."""
        sample = _Sample(name="foo", count=-1)
        assert sample.is_valid() is False


class TestValidityCheck:
    """validity_check() packages is_valid() into a CheckTuple."""

    def test_valid_instance_tuple(self) -> None:
        """A valid instance produces (True, name, instance)."""
        sample = _Sample(name="foo", count=5)
        passed, field_name, observed = sample.validity_check("nested")
        assert passed is True
        assert field_name == "nested"
        assert observed is sample

    def test_invalid_instance_tuple(self) -> None:
        """An invalid instance produces (False, name, instance)."""
        sample = _Sample(name="foo", count=-1)
        passed, field_name, observed = sample.validity_check("nested")
        assert passed is False
        assert field_name == "nested"
        assert observed is sample


# ---------------------------------------------------------------------------
# _Validated._structural_checks default
# ---------------------------------------------------------------------------


class TestStructuralChecksDefault:
    """The base class default returns an empty tuple."""

    def test_default_returns_empty_tuple(self) -> None:
        """_Validated._structural_checks(instance) returns ()."""
        instance = _NoStructuralRules(value=5)
        # pylint: disable=protected-access
        assert not _Validated._structural_checks(instance)

    def test_default_is_strict_tuple(self) -> None:
        """The default is exactly () — not None, not a list."""
        instance = _NoStructuralRules(value=5)
        # pylint: disable=protected-access
        result = _Validated._structural_checks(instance)
        assert isinstance(result, tuple)
        assert len(result) == 0
