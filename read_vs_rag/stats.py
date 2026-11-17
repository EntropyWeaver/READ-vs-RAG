"""Paired inference. Questions are the resampling unit, never repeated model calls."""

import math
import random
import statistics


def quantile(values, p):
    if not values:
        return None
    x = sorted(values)
    pos = (len(x) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return x[lo] + (x[hi] - x[lo]) * (pos - lo)


def distribution(values):
    x = [v for v in values if v is not None]
    if not x:
        return {"n": 0, "mean": None, "p50": None, "p95": None, "p99": None, "total": None}
    return {"n": len(x), "mean": statistics.mean(x), "p50": quantile(x, .5),
            "p95": quantile(x, .95), "p99": quantile(x, .99), "total": sum(x)}


def wilson(successes, n, z=1.959963984540054):
    if not 0 <= successes <= n:
        raise ValueError("Invalid success count")
    if not n:
        return {"n": 0, "mean": None, "low": None, "high": None}
    p = successes / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"n": n, "mean": p, "low": max(0., centre - half), "high": min(1., centre + half)}


def bootstrap_mean(values, samples=10000, seed=20261117):
    if samples < 100:
        raise ValueError("Use at least 100 bootstrap samples")
    if not values:
        return {"n": 0, "mean": None, "low": None, "high": None}
    rng, n = random.Random(seed), len(values)
    means = [sum(rng.choices(values, k=n)) / n for _ in range(samples)]
    return {"n": n, "mean": statistics.mean(values), "low": quantile(means, .025),
            "high": quantile(means, .975)}


def mcnemar(a, b):
    if len(a) != len(b) or any(type(v) is not bool for v in [*a, *b]):
        raise ValueError("McNemar requires aligned binary observations")
    wins = sum(x and not y for x, y in zip(a, b))
    losses = sum(y and not x for x, y in zip(a, b))
    d = wins + losses
    p = min(1., 2 * sum(math.comb(d, j) for j in range(min(wins, losses) + 1)) / 2 ** d)
    return {"n_pairs": len(a), "wins": wins, "losses": losses, "ties": len(a) - d, "p_raw": p}


def holm(pvalues):
    last, out, n = 0., {}, len(pvalues)
    for i, (key, p) in enumerate(sorted(pvalues.items(), key=lambda x: x[1])):
        if not 0 <= p <= 1:
            raise ValueError("Invalid p value")
        last = min(1., max(last, (n - i) * p))
        out[key] = last
    return out


def paired_comparison(reference, other, samples=10000):
    """Maps question_id -> list of repeats, with complete matching repeat IDs checked by caller.

    CIs bootstrap per-question mean differences. McNemar only when each question
    has exactly one binary observation; repeated runs are NOT extra questions.
    """
    common = sorted(reference.keys() & other.keys())
    diffs = [statistics.mean(reference[q]) - statistics.mean(other[q]) for q in common]
    result = {"delta": bootstrap_mean(diffs, samples), "n_questions": len(common),
              "missing_reference": len(other.keys() - reference.keys()),
              "missing_other": len(reference.keys() - other.keys()), "mcnemar": None}
    if common and all(len(reference[q]) == len(other[q]) == 1 for q in common):
        result["mcnemar"] = mcnemar([bool(reference[q][0]) for q in common],
                                    [bool(other[q][0]) for q in common])
    return result
