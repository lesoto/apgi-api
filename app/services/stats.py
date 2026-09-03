"""
Pure-Python statistics helpers (norms percentiles/CIs, Cronbach's alpha,
and the longitudinal metrics in Phase 5) — deliberately no numpy/scipy
dependency for a handful of textbook formulas that don't need one.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Sequence


def percentile_rank(sample: Sequence[float], value: float) -> float:
    """Percentage of `sample` at or below `value` (0-100)."""
    if not sample:
        raise ValueError("sample must be non-empty")
    at_or_below = sum(1 for x in sample if x <= value)
    return 100.0 * at_or_below / len(sample)


def bootstrap_percentile_ci(
    sample: Sequence[float],
    value: float,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """A bootstrap confidence interval on the percentile rank of `value`
    within `sample`: resample `sample` with replacement `n_resamples` times,
    recompute the percentile rank each time, and take the empirical
    interval. Deterministic given `seed` so results are reproducible.
    """
    if len(sample) < 2:
        rank = percentile_rank(sample, value) if sample else 50.0
        return (rank, rank)

    rng = random.Random(seed)
    n = len(sample)
    resampled_ranks = []
    for _ in range(n_resamples):
        resample = [sample[rng.randrange(n)] for _ in range(n)]
        resampled_ranks.append(percentile_rank(resample, value))

    resampled_ranks.sort()
    alpha = 1 - confidence
    lower_idx = max(0, int((alpha / 2) * n_resamples))
    upper_idx = min(n_resamples - 1, int((1 - alpha / 2) * n_resamples) - 1)
    return (resampled_ranks[lower_idx], resampled_ranks[upper_idx])


def two_phase_contrast(
    group_a: Sequence[float], group_b: Sequence[float], n_permutations: int = 5000, seed: int = 0
) -> dict[str, float]:
    """Compare two n-of-1 phases: mean difference, Cohen's d (pooled SD),
    and a two-sided permutation-test p-value — appropriate for the small,
    non-normal samples typical of a single-subject design, without assuming
    a parametric distribution the way a t-test would.
    """
    if len(group_a) < 1 or len(group_b) < 1:
        raise ValueError("Both phases need at least one observation.")

    mean_a, mean_b = statistics.mean(group_a), statistics.mean(group_b)
    observed_diff = mean_b - mean_a

    if len(group_a) > 1 and len(group_b) > 1:
        var_a, var_b = statistics.variance(group_a), statistics.variance(group_b)
        n_a, n_b = len(group_a), len(group_b)
        pooled_sd = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
        cohens_d = observed_diff / pooled_sd if pooled_sd > 0 else 0.0
    else:
        cohens_d = 0.0

    rng = random.Random(seed)
    pooled = list(group_a) + list(group_b)
    n_a = len(group_a)
    at_least_as_extreme = 0
    for _ in range(n_permutations):
        rng.shuffle(pooled)
        perm_a, perm_b = pooled[:n_a], pooled[n_a:]
        perm_diff = statistics.mean(perm_b) - statistics.mean(perm_a)
        if abs(perm_diff) >= abs(observed_diff):
            at_least_as_extreme += 1
    p_value = at_least_as_extreme / n_permutations

    return {
        "mean_difference": round(observed_diff, 4),
        "cohens_d": round(cohens_d, 4),
        "p_value": round(p_value, 4),
    }


def cronbachs_alpha(item_matrix: Sequence[Sequence[float]]) -> float:
    """Cronbach's alpha for internal consistency reliability.

    `item_matrix` is one row per respondent (session), one column per item
    (trial); every row must have the same length. Returns NaN-safe 0.0 for
    degenerate inputs (fewer than 2 items or 2 respondents, or zero total
    variance) rather than raising, since callers surface this to an API
    response and a degenerate reliability estimate is a valid — if
    uninformative — answer, not an error.
    """
    n_respondents = len(item_matrix)
    if n_respondents < 2:
        return 0.0
    k = len(item_matrix[0])
    if k < 2 or any(len(row) != k for row in item_matrix):
        return 0.0

    item_variances = []
    for j in range(k):
        column = [row[j] for row in item_matrix]
        item_variances.append(statistics.pvariance(column))

    total_scores = [sum(row) for row in item_matrix]
    total_variance = statistics.pvariance(total_scores)
    if total_variance == 0:
        return 0.0

    alpha = (k / (k - 1)) * (1 - sum(item_variances) / total_variance)
    return round(alpha, 4)
