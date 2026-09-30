"""Bootstrap confidence intervals. Seeded, so reports are reproducible."""

from __future__ import annotations

import random


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def bootstrap_ci(
    values: list[float], resamples: int = 2000, seed: int = 7, level: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = [sum(rng.choices(values, k=n)) / n for _ in range(resamples)]
    tail = (1 - level) / 2 * 100
    return (percentile(means, tail), percentile(means, 100 - tail))


def paired_difference_ci(
    a: list[float], b: list[float], resamples: int = 2000, seed: int = 7, level: float = 0.95
) -> tuple[float, float]:
    """Interval for mean(a - b) when a[i] and b[i] are scores on the same case."""
    if len(a) != len(b):
        raise ValueError("Paired samples must have the same length")
    return bootstrap_ci([x - y for x, y in zip(a, b, strict=True)], resamples, seed, level)
