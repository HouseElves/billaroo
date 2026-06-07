"""Tests for synthetic_billing.contracts.id_contracts."""

import pytest

from synthetic_billing.contracts.id_contracts import derive_id


class TestDeriveIdHappyPath:
    """derive_id returns a 16-char lowercase hex string."""

    def test_returns_sixteen_chars(self) -> None:
        """Output length is exactly 16 characters."""
        result = derive_id("account", "00000001")
        assert len(result) == 16

    def test_returns_lowercase_hex(self) -> None:
        """Every character is in the lowercase hex alphabet."""
        result = derive_id("account", "00000001")
        assert all(c in "0123456789abcdef" for c in result)

    def test_accepts_single_field(self) -> None:
        """A single string field is a valid derivation input."""
        result = derive_id("sentinel")
        assert len(result) == 16

    def test_accepts_integer_ordinal(self) -> None:
        """Zero is a valid non-negative integer ordinal."""
        result = derive_id("account", 0)
        assert len(result) == 16

    def test_accepts_positive_integer_ordinal(self) -> None:
        """Positive integers are valid ordinals."""
        result = derive_id("subscriber", 12345)
        assert len(result) == 16

    def test_accepts_unicode(self) -> None:
        """Non-ASCII strings hash cleanly via UTF-8 encoding."""
        result = derive_id("naïve", "café")
        assert len(result) == 16


class TestDeriveIdDeterminism:
    """Same inputs must always produce the same ID."""

    def test_same_inputs_same_output(self) -> None:
        """Repeated calls with identical args return the same hex string."""
        first = derive_id("account", "00000001")
        second = derive_id("account", "00000001")
        assert first == second

    def test_field_order_matters(self) -> None:
        """Swapping field positions changes the derived ID."""
        forward = derive_id("account", "1")
        backward = derive_id("1", "account")
        assert forward != backward

    def test_string_int_share_canonical_form(self) -> None:
        """Int 1 canonicalizes to '1', matching the string '1'."""
        assert derive_id("account", 1) == derive_id("account", "1")

    def test_different_entity_prefixes_distinct(self) -> None:
        """IDs from different entity families do not collide."""
        acct = derive_id("account", "1")
        sub = derive_id("subscriber", "1")
        assert acct != sub

    def test_separator_is_canonical(self) -> None:
        """Colon-joined multi-field input differs from concatenated single-field."""
        assert derive_id("a", "b") != derive_id("ab")
        assert derive_id("a", "b") != derive_id("a-b")


class TestDeriveIdRejection:
    """derive_id refuses unsafe or malformed inputs."""

    def test_rejects_no_fields(self) -> None:
        """At least one field is required."""
        with pytest.raises(ValueError, match="at least one field"):
            derive_id()

    def test_rejects_empty_string(self) -> None:
        """An empty string is blank and rejected."""
        with pytest.raises(ValueError, match="blank"):
            derive_id("account", "")

    def test_rejects_whitespace_string(self) -> None:
        """A whitespace-only string is blank and rejected."""
        with pytest.raises(ValueError, match="blank"):
            derive_id("account", "   ")

    def test_rejects_colon_in_string(self) -> None:
        """Embedded colons would corrupt the canonical separator."""
        with pytest.raises(ValueError, match="':'"):
            derive_id("account", "with:colon")

    def test_rejects_negative_ordinal(self) -> None:
        """Negative integers are invalid ordinals."""
        with pytest.raises(ValueError, match="non-negative"):
            derive_id("account", -1)

    def test_rejects_bool_true(self) -> None:
        """Bool True is rejected despite being an int subclass."""
        with pytest.raises(TypeError, match="bool"):
            derive_id("account", True)

    def test_rejects_bool_false(self) -> None:
        """Bool False is rejected despite being an int subclass."""
        with pytest.raises(TypeError, match="bool"):
            derive_id("account", False)

    def test_rejects_float(self) -> None:
        """Float is not a valid field type."""
        with pytest.raises(TypeError, match="str or int"):
            derive_id("account", 3.14)  # type: ignore[arg-type]

    def test_rejects_none(self) -> None:
        """None is not a valid field type."""
        with pytest.raises(TypeError, match="str or int"):
            derive_id("account", None)  # type: ignore[arg-type]

    def test_rejects_bytes(self) -> None:
        """Bytes are not a valid field type."""
        with pytest.raises(TypeError, match="str or int"):
            derive_id("account", b"bytes")  # type: ignore[arg-type]
