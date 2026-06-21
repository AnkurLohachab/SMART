"""Inter-extractor agreement (Cohen's kappa) over equivalence-class membership."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable

from lib.types import CanonicalProvision


def cohens_kappa(a: list[bool], b: list[bool]) -> float:
    """Cohen's kappa for two equal-length 0/1 vectors."""
    assert len(a) == len(b), "vectors must be same length"
    n = len(a)
    if n == 0:
        return 1.0
    agree = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1 = sum(a) / n
    pb1 = sum(b) / n
    expected = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if expected >= 1.0:
        return 1.0 if agree == 1.0 else 0.0
    return (agree - expected) / (1 - expected)


def membership_matrix(per_extractor: dict[str, list[CanonicalProvision]]) \
        -> tuple[list[tuple[str, str, str]], dict[str, list[bool]]]:
    """Build the union of triples and per-extractor membership vectors."""
    union: set[tuple[str, str, str]] = set()
    by_extractor: dict[str, set[tuple[str, str, str]]] = {}
    for name, rows in per_extractor.items():
        s = {r.triple for r in rows}
        by_extractor[name] = s
        union |= s
    triples = sorted(union)
    vectors = {
        name: [t in s for t in triples]
        for name, s in by_extractor.items()
    }
    return triples, vectors


def pairwise_kappa(per_extractor: dict[str, list[CanonicalProvision]]) -> list[dict]:
    """Cohen's kappa on the membership matrix for every extractor pair."""
    _, vectors = membership_matrix(per_extractor)
    rows = []
    for a, b in combinations(sorted(vectors), 2):
        kappa = cohens_kappa(vectors[a], vectors[b])
        n_a = sum(vectors[a])
        n_b = sum(vectors[b])
        intersect = sum(1 for x, y in zip(vectors[a], vectors[b]) if x and y)
        rows.append({
            "extractor_a": a,
            "extractor_b": b,
            "n_a": n_a,
            "n_b": n_b,
            "n_intersect": intersect,
            "n_union": sum(1 for x, y in zip(vectors[a], vectors[b]) if x or y),
            "kappa": round(kappa, 4),
        })
    return rows
