"""Join provisions to SMART section/component via coverage.csv."""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from typing import Iterable

from lib.types import CanonicalProvision
from lib.vocabulary import Vocabulary


def coverage_per_provision(provisions: Iterable[CanonicalProvision],
                           vocab: Vocabulary) -> list[dict]:
    cov_lookup: dict[str, dict] = {row["artefact"]: row for row in vocab.coverage}
    rows: list[dict] = []
    for r in provisions:
        cov = cov_lookup.get(r.artefact)
        rows.append({
            "bearer": r.bearer,
            "predicate": r.predicate,
            "artefact": r.artefact,
            "n_sources": len(r.sources),
            "covered": bool(cov) and r.artefact != "Unknown_Artefact",
            "smart_section": (cov or {}).get("smart_section", ""),
            "smart_component": (cov or {}).get("smart_component", ""),
            "extractors": ";".join(r.extractors),
        })
    return rows


def grouped_for_paper(provisions: Iterable[CanonicalProvision],
                      vocab: Vocabulary) -> list[dict]:
    """Group by (artefact, smart_section): one row per category with combined sources."""
    cov_lookup: dict[str, dict] = {row["artefact"]: row for row in vocab.coverage}
    groups: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"sources": set(), "n_provisions": 0}
    )
    for r in provisions:
        cov = cov_lookup.get(r.artefact, {})
        key = (r.artefact, cov.get("smart_section", ""))
        g = groups[key]
        g["n_provisions"] += 1
        for doc, _ in r.sources:
            g["sources"].add(doc)
    out: list[dict] = []
    for (artefact, section), g in sorted(groups.items()):
        cov = cov_lookup.get(artefact, {})
        out.append({
            "artefact": artefact,
            "smart_section": section,
            "smart_component": cov.get("smart_component", ""),
            "sources": ";".join(sorted(g["sources"])),
            "n_provisions": g["n_provisions"],
            "note": cov.get("note", ""),
        })
    return out
