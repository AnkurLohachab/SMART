"""Closed subsumption ontology with per-slot transitive closure; cycles raise ValueError."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from lib.types import CanonicalProvision

VOCAB = Path(__file__).resolve().parent.parent / "vocabulary"


@lru_cache(maxsize=1)
def _load_table() -> dict[str, dict[str, frozenset[str]]]:
    """Return {slot: {sub: frozenset(transitive supers)}}."""
    direct: dict[str, dict[str, set[str]]] = {"bearer": {}, "predicate": {}, "artefact": {}, "modal": {}}
    p = VOCAB / "subsumption.csv"
    if not p.exists():
        return {k: {} for k in direct}
    with p.open() as fh:
        for row in csv.DictReader(fh):
            slot = row["slot"].strip()
            sub = row["sub"].strip()
            sup = row["super"].strip()
            if slot not in direct:
                continue
            direct[slot].setdefault(sub, set()).add(sup)

    closure: dict[str, dict[str, frozenset[str]]] = {}
    for slot, edges in direct.items():
        c: dict[str, set[str]] = {k: set(v) for k, v in edges.items()}
        changed = True
        while changed:
            changed = False
            for sub in list(c.keys()):
                for sup in list(c[sub]):
                    if sup in c:
                        new = c[sup] - c[sub]
                        if new:
                            c[sub] |= new
                            changed = True
        for sub, supers in c.items():
            if sub in supers:
                raise ValueError(f"subsumption cycle in slot {slot!r}: {sub!r}")
        closure[slot] = {k: frozenset(v) for k, v in c.items()}
    return closure


def ancestors(slot: str, value: str) -> frozenset[str]:
    return _load_table().get(slot, {}).get(value, frozenset())


def is_subsumed_by(slot: str, sub: str, sup: str) -> bool:
    if sub == sup:
        return True
    return sup in ancestors(slot, sub)


def formally_equivalent(a: CanonicalProvision, b: CanonicalProvision) -> bool:
    return a.triple == b.triple


def formally_subsumed(a: CanonicalProvision, b: CanonicalProvision) -> bool:
    return (is_subsumed_by("bearer", a.bearer, b.bearer)
            and is_subsumed_by("predicate", a.predicate, b.predicate)
            and is_subsumed_by("artefact", a.artefact, b.artefact))
