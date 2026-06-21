"""Sort merged provisions into a stable partition and assert distinctness."""
from __future__ import annotations

from typing import Iterable

from lib.types import CanonicalProvision


def partition(provisions: Iterable[CanonicalProvision]) -> list[CanonicalProvision]:
    """Return the input sorted by triple, asserting no duplicates."""
    rows = sorted(provisions, key=lambda r: r.triple)
    seen = set()
    for r in rows:
        if r.triple in seen:
            raise ValueError(
                f"partition invariant broken: triple {r.triple} appeared twice "
                "after canonicalise"
            )
        seen.add(r.triple)
    return rows


def equivalence_relation_holds(triples: list[tuple[str, str, str]]) -> bool:
    """Check reflexivity, symmetry, and transitivity of triple identity."""
    for t in triples:
        if not (t == t):
            return False
    for a in triples:
        for b in triples:
            if (a == b) != (b == a):
                return False
    for a in triples:
        for b in triples:
            for c in triples:
                if a == b and b == c and a != c:
                    return False
    return True
