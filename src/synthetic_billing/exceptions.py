"""
Exception hierarchy for synthetic subscriber billing.

The hierarchy is deliberately shallow. New branches are added only when
modules actually raise them; no speculative placeholders live here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class SyntheticBillingError(Exception):
    """Base class for every exception raised by synthetic_billing."""


class ValidationError(SyntheticBillingError):
    """Raised when typed project data fails validation."""


class InvalidRequestError(ValidationError):
    """Raised when a typed request or domain object fails validation.

    The ``violations`` attribute records offending member names and values.
    """

    def __init__(
        self,
        message: str,
        *,
        violations: Sequence[tuple[str, Any]] | None = None,
    ) -> None:
        """Initialize the error with a message and optional violations."""
        super().__init__(message)
        self.violations = tuple(violations or ())
