"""Tests for synthetic_billing.simulate.random_stream."""

import pytest

from synthetic_billing.simulate.random_stream import RandomStream


class TestRandomStreamDeterminism:
    """Same seed must produce the same sequence (design constitution rule 1)."""

    def test_same_seed_same_sequence(self) -> None:
        a = RandomStream(seed=123)
        b = RandomStream(seed=123)
        assert [a.random() for _ in range(50)] == [b.random() for _ in range(50)]

    def test_different_seeds_differ(self) -> None:
        a = RandomStream(seed=1)
        b = RandomStream(seed=2)
        assert [a.random() for _ in range(20)] != [b.random() for _ in range(20)]

    def test_choice_deterministic(self) -> None:
        items = ["a", "b", "c", "d"]
        a = RandomStream(seed=99)
        b = RandomStream(seed=99)
        assert [a.choice(items) for _ in range(30)] == [
            b.choice(items) for _ in range(30)
        ]

    def test_choices_deterministic(self) -> None:
        items = [1, 2, 3, 4, 5]
        a = RandomStream(seed=7)
        b = RandomStream(seed=7)
        assert a.choices(items, k=20) == b.choices(items, k=20)

    def test_randint_deterministic(self) -> None:
        a = RandomStream(seed=55)
        b = RandomStream(seed=55)
        assert [a.randint(0, 100) for _ in range(30)] == [
            b.randint(0, 100) for _ in range(30)
        ]


class TestRandomStreamValidation:
    """Seed validation."""

    def test_rejects_bool_seed(self) -> None:
        with pytest.raises(TypeError, match="bool"):
            RandomStream(seed=True)

    def test_rejects_str_seed(self) -> None:
        with pytest.raises(TypeError, match="int"):
            RandomStream(seed="42")  # type: ignore[arg-type]

    def test_rejects_float_seed(self) -> None:
        with pytest.raises(TypeError, match="int"):
            RandomStream(seed=3.14)  # type: ignore[arg-type]

    def test_seed_property(self) -> None:
        rs = RandomStream(seed=999)
        assert rs.seed == 999
