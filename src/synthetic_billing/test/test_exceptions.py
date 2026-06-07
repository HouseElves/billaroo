"""Tests for synthetic_billing.exceptions."""

import pytest

from synthetic_billing.exceptions import (
    InvalidRequestError,
    SyntheticBillingError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Project exceptions form a shallow chain rooted at SyntheticBillingError."""

    def test_synthetic_billing_error_subclasses_exception(self) -> None:
        """SyntheticBillingError is the project's root Exception subclass."""
        assert issubclass(SyntheticBillingError, Exception)

    def test_validation_error_subclasses_root(self) -> None:
        """ValidationError sits under the project root."""
        assert issubclass(ValidationError, SyntheticBillingError)

    def test_invalid_request_error_subclasses_validation_error(self) -> None:
        """InvalidRequestError is a ValidationError specialization."""
        assert issubclass(InvalidRequestError, ValidationError)

    def test_isinstance_chain(self) -> None:
        """An InvalidRequestError satisfies every ancestor isinstance check."""
        err = InvalidRequestError("bad")
        assert isinstance(err, InvalidRequestError)
        assert isinstance(err, ValidationError)
        assert isinstance(err, SyntheticBillingError)
        assert isinstance(err, Exception)


class TestInvalidRequestErrorConstruction:
    """InvalidRequestError stores a message and an optional violations tuple."""

    def test_message_set(self) -> None:
        """The message passed to the constructor is the str() of the error."""
        err = InvalidRequestError("bad input")
        assert str(err) == "bad input"

    def test_violations_default_empty_tuple(self) -> None:
        """Omitting violations defaults to an empty tuple."""
        err = InvalidRequestError("bad")
        assert not err.violations
        assert isinstance(err.violations, tuple)

    def test_violations_none_becomes_empty(self) -> None:
        """Explicit None for violations is normalized to an empty tuple."""
        err = InvalidRequestError("bad", violations=None)
        assert not err.violations
        assert isinstance(err.violations, tuple)

    def test_violations_list_normalized_to_tuple(self) -> None:
        """A list of violations is stored as an immutable tuple."""
        err = InvalidRequestError("bad", violations=[("field", 42)])
        assert err.violations == (("field", 42),)
        assert isinstance(err.violations, tuple)

    def test_multiple_violations(self) -> None:
        """Multiple violations are preserved in order."""
        err = InvalidRequestError(
            "bad",
            violations=[("a", 1), ("b", 2), ("c", 3)],
        )
        assert err.violations == (("a", 1), ("b", 2), ("c", 3))


class TestInvalidRequestErrorRaising:
    """InvalidRequestError behaves as a normal exception when raised."""

    def test_raisable(self) -> None:
        """The error can be raised and caught by its own class."""
        with pytest.raises(InvalidRequestError):
            raise InvalidRequestError("bad")

    def test_caught_as_validation_error(self) -> None:
        """The error can be caught as a ValidationError."""
        with pytest.raises(ValidationError):
            raise InvalidRequestError("bad")

    def test_caught_as_root(self) -> None:
        """The error can be caught as a SyntheticBillingError."""
        with pytest.raises(SyntheticBillingError):
            raise InvalidRequestError("bad")

    def test_violations_accessible_on_caught_error(self) -> None:
        """A caught error exposes its violations attribute."""
        with pytest.raises(InvalidRequestError) as exc_info:
            raise InvalidRequestError("bad", violations=[("f", 1)])
        assert exc_info.value.violations == (("f", 1),)
