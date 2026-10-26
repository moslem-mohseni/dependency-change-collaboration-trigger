"""Shared statistics helpers (copied into each paper's src/ so folders stay isolated)."""
from __future__ import annotations

import math
import random
from typing import Sequence

import numpy as np


def mean_ci(x: Sequence[float], n_boot: int = 2000, seed: int = 0, alpha: float = 0.05):
    """Mean with a percentile bootstrap (1-alpha) confidence interval."""
    a = np.asarray(x, dtype=float)
    if a.size == 0:
        return float("nan"), float("nan"), float("nan")
    if a.size == 1 or np.all(a == a[0]):
        return float(a.mean()), float(a.mean()), float(a.mean())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    means = a[idx].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(a.mean()), float(lo), float(hi)


def paired_diff_ci(a: Sequence[float], b: Sequence[float], n_boot: int = 2000, seed: int = 0):
    """Paired difference a-b: mean, CI, and Cohen's d_z (on paired differences)."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    m, lo, hi = mean_ci(d, n_boot=n_boot, seed=seed)
    sd = d.std(ddof=1) if d.size > 1 else float("nan")
    dz = m / sd if sd and not math.isnan(sd) and sd > 0 else float("nan")
    return m, lo, hi, dz


def sign_flip_p(a: Sequence[float], b: Sequence[float], n_perm: int = 5000, seed: int = 0):
    """Two-sided paired sign-flip permutation test p-value on mean difference."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    obs = abs(d.mean())
    if obs == 0:
        return 1.0
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_perm, d.size))
    perm = np.abs((signs * d).mean(axis=1))
    return float((np.sum(perm >= obs - 1e-15) + 1) / (n_perm + 1))


def holm(pvals: Sequence[float]):
    """Holm-Bonferroni adjusted p-values (same order as input)."""
    p = np.asarray(pvals, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval for a proportion."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, c - h, c + h
