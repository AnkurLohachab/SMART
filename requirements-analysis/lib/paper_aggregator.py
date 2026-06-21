"""Aggregate atomic provisions into the paper-side categories via the subsumption ontology."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from lib import paper_audit as pa
from lib import subsumption as sub
from lib.types import CanonicalProvision

OUT = Path(__file__).resolve().parent.parent / "sample_results"


def aggregate(provisions: Iterable[CanonicalProvision]) -> dict:
    table: dict[str, list[CanonicalProvision]] = defaultdict(list)
    additional: list[CanonicalProvision] = []
    ambiguous: list[tuple[CanonicalProvision, list[str]]] = []

    paper_artefacts = [(label, art) for label, art in pa.PAPER_CATEGORIES]

    for prov in provisions:
        matches = [label for label, art in paper_artefacts
                   if sub.is_subsumed_by("artefact", prov.artefact, art)]
        if len(matches) == 1:
            table[matches[0]].append(prov)
        elif len(matches) > 1:
            ambiguous.append((prov, matches))
            for m in matches:
                table[m].append(prov)
        else:
            additional.append(prov)

    per_category = {}
    for label, _expected_art in paper_artefacts:
        provs = table.get(label, [])
        per_category[label] = {
            "atomic_count": len(provs),
            "distinct_extractors": sorted({e for p in provs for e in p.extractors}),
            "examples": [
                {"triple": list(p.triple), "n_sources": len(p.sources)}
                for p in provs[:5]
            ],
        }
    return {
        "per_category": per_category,
        "additional": [
            {"triple": list(p.triple), "extractors": list(p.extractors),
             "n_sources": len(p.sources)}
            for p in additional
        ],
        "ambiguous": [
            {"triple": list(p.triple), "matches": labels}
            for p, labels in ambiguous
        ],
        "n_paper_categories": len(paper_artefacts),
        "n_atomic": sum(len(v) for v in table.values()) + len(additional),
    }


def write(provisions: Iterable[CanonicalProvision]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = aggregate(provisions)
    p = OUT / "paper_aggregation.json"
    p.write_text(json.dumps(payload, indent=2))
    return p
