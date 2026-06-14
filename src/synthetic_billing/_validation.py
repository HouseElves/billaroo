"""
Private validation protocol and helpers.

This module defines the shared validation vocabulary used across typed
application objects. Domain modules produce checks; this module consumes them.

The module intentionally does not own domain rules such as catalog membership,
billing semantics, or lifecycle policy.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Self, TypeAlias

from synthetic_billing.exceptions import InvalidRequestError


CheckTuple: TypeAlias = tuple[bool, str, Any]
"""Validation check tuple: (criterion-passed, field-name, observed-value)."""


CheckSpec: TypeAlias = tuple[str, type] | tuple[str, type, type]
"""
Type check specification.

Shape is ``(field-name, required-type)`` or
``(field-name, required-type, excluded-type)``. The optional third element
rejects values that are instances of the excluded type, even when they pass
the required-type check. The canonical use is rejecting bool for int fields.
"""


def raise_on_violations(checks: Sequence[CheckTuple], message: str) -> None:
    """Raise InvalidRequestError when any validation check fails."""
    violations = tuple(
        (field_name, observed_value)
        for passed, field_name, observed_value in checks
        if not passed
    )
    if violations:
        raise InvalidRequestError(message, violations=violations)


class _Validated:
    """
    Mix-in providing validation helpers for frozen dataclasses.

    Subclasses declare constructor type-check specifications as a class
    attribute and may override ``_structural_checks`` to add value-range or
    shape rules.

    Construction boundary (D41). Production code builds ``_Validated``
    records through :meth:`create_validated` or an established model
    builder; direct dataclass construction is not a supported production
    path. Direct construction is reserved for tests that need a
    deliberately invalid instance. A project-level guard
    (``test_validated_construction_guard``) enforces this on non-test
    source.

    Validation layering. :meth:`create_validated` runs constructor type
    checks (``_type_check_specs``) and then calls :meth:`validate`.
    :meth:`validate` checks structural and value invariants of an
    already type-correct instance; it does not replay the constructor
    type checks. A directly constructed test instance is therefore
    expected to be type-correct at the field level (the invalidity it
    demonstrates lives in structural or value rules, not in argument
    types), except where a subclass's ``_structural_checks`` adds its
    own defensive ``isinstance`` re-checks for safely-observable
    reporting under constitution rule 23.

    Domain rules do not belong here. External modules may produce additional
    checks and pass them to :func:`raise_on_violations` directly.
    """

    _type_check_specs: ClassVar[tuple[CheckSpec, ...]] = ()

    @classmethod
    def create_validated(cls, *args: Any) -> Self:
        """Build the dataclass, run constructor type checks, then validate.

        This is the supported production construction path (D41): it
        confirms the argument count, runs the constructor type checks
        from ``_type_check_specs``, constructs the instance, and then
        runs :meth:`validate` for structural and value invariants.
        """
        expected_count = len(cls._type_check_specs)
        actual_count = len(args)
        if actual_count != expected_count:
            raise TypeError(
                f"{cls.__name__}.create_validated() expected "
                f"{expected_count} arguments but received {actual_count}"
            )

        raise_on_violations(
            cls._constructor_type_checks(args),
            f"Invalid constructor argument types for `{cls.__name__}`",
        )

        instance = cls(*args)
        instance.validate()
        return instance

    @classmethod
    def _constructor_type_checks(
        cls,
        args: Sequence[Any],
    ) -> tuple[CheckTuple, ...]:
        """Return constructor-argument type checks for the provided args."""
        checks: list[CheckTuple] = []
        for index, spec in enumerate(cls._type_check_specs):
            field_name, required_type, *excluded_type = spec
            value = args[index]
            is_required_type = isinstance(value, required_type)
            is_excluded_type = bool(excluded_type) and isinstance(
                value,
                excluded_type[0],
            )
            checks.append(
                (
                    is_required_type and not is_excluded_type,
                    field_name,
                    value,
                )
            )
        return tuple(checks)

    def validate(self) -> None:
        """Apply structural checks declared by the subclass.

        Checks structural and value invariants of an already
        type-correct instance; it does not replay the constructor type
        checks from ``_type_check_specs`` (D41). Subclasses whose
        ``_structural_checks`` include defensive ``isinstance``
        re-checks do so to keep violations safely observable under
        constitution rule 23, not to re-run constructor type checking.
        """
        raise_on_violations(
            self._structural_checks(),
            f"Invalid data in a `{type(self).__name__}` instance",
        )

    def is_valid(self) -> bool:
        """Return whether this instance passes structural validation."""
        try:
            self.validate()
        except InvalidRequestError:
            return False
        return True

    def validity_check(self, field_name: str) -> CheckTuple:
        """Return a check tuple representing whether this instance is valid."""
        return self.is_valid(), field_name, self

    def _structural_checks(self) -> tuple[CheckTuple, ...]:
        """Return structural validation checks for this instance."""
        return ()
