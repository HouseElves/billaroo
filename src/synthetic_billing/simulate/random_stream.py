"""Centralized seeded random stream.

All stochastic decisions in the simulator flow through a RandomStream
instance so that runs are reproducible for a given seed (design
constitution rule 14).
"""

from __future__ import annotations

import random as _random_mod
from typing import Sequence, TypeVar

__all__ = ["RandomStream"]

T = TypeVar("T")


class RandomStream:
    """A thin seeded wrapper around ``random.Random``.

    The wrapper exists so that no code in the project calls module-level
    random functions directly.  Every stochastic call goes through an
    explicit ``RandomStream`` instance whose seed is recorded in the
    scenario config.
    """

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool):
            raise TypeError(f"seed must be int, not bool: {seed!r}")
        if not isinstance(seed, int):
            raise TypeError(f"seed must be int, got {type(seed).__name__}")
        self._seed = seed
        self._rng = _random_mod.Random(seed)

    @property
    def seed(self) -> int:
        return self._seed

    def random(self) -> float:
        """Return a float in [0.0, 1.0)."""
        return self._rng.random()

    def choice(self, seq: Sequence[T]) -> T:
        """Return a random element from *seq*."""
        return self._rng.choice(seq)

    def choices(self, population: Sequence[T], *, k: int = 1) -> list[T]:
        """Return *k* elements from *population* with replacement."""
        return self._rng.choices(population, k=k)

    def randint(self, a: int, b: int) -> int:
        """Return a random integer N such that a <= N <= b."""
        return self._rng.randint(a, b)
