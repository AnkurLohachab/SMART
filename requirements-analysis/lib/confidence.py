"""Per-provision confidence: self-consistency, cross-model support, judge score."""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from lib.types import CanonicalProvision

_NAME_TEMP_RE = re.compile(r"@T(?P<t>[0-9.]+)#(?P<s>\d+)$")


def _parse_extractor_name(name: str) -> tuple[str, float | None, int | None]:
    """deepinfra[model]@T0.3#1 parses to (deepinfra[model], 0.3, 1)."""
    m = _NAME_TEMP_RE.search(name)
    if not m:
        return name, None, None
    base = name[: m.start()]
    return base, float(m.group("t")), int(m.group("s"))


def aggregate(provisions: Iterable[CanonicalProvision],
              total_runs_per_model: dict[str, int]) -> list[dict]:
    """Compute per-class confidence numbers; total_runs_per_model is the self-consistency denominator."""
    rows: list[dict] = []
    for prov in provisions:
        triple = prov.triple
        per_model_hits: dict[str, set[tuple[float, int]]] = defaultdict(set)
        regex_hit = False
        for ext in prov.extractors:
            if ext.startswith("regex"):
                regex_hit = True
                continue
            base, T, S = _parse_extractor_name(ext)
            if T is None:
                per_model_hits[base].add((-1.0, 0))
            else:
                per_model_hits[base].add((T, S))

        cross_model_support = len(per_model_hits)

        per_model_consistency: dict[str, float] = {}
        for model, hits in per_model_hits.items():
            denom = total_runs_per_model.get(model, len(hits))
            per_model_consistency[model] = len(hits) / max(denom, 1)
        self_consistency = max(per_model_consistency.values()) if per_model_consistency else 0.0

        all_T = sorted({T for hits in per_model_hits.values() for (T, _S) in hits if T >= 0})
        if not all_T:
            temp_band = "regex_only" if regex_hit else "unknown"
        elif all_T == [0.0]:
            temp_band = "core"
        elif all(T <= 0.3 for T in all_T):
            temp_band = "near-core"
        else:
            temp_band = "exploratory"

        rows.append({
            "bearer": prov.bearer,
            "predicate": prov.predicate,
            "artefact": prov.artefact,
            "n_sources": len(prov.sources),
            "regex_hit": regex_hit,
            "cross_model_support": cross_model_support,
            "self_consistency": round(self_consistency, 3),
            "temperature_band": temp_band,
            "extractors": ";".join(sorted(set(prov.extractors))),
        })
    return rows


def core_set(rows: list[dict],
             min_self_consistency: float = 0.6,
             min_cross_model_support: int = 2) -> list[dict]:
    """Filter to high-confidence 'core' provisions for headline reporting."""
    return [
        r for r in rows
        if r["cross_model_support"] >= min_cross_model_support
        and r["self_consistency"] >= min_self_consistency
    ]


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("no provisions\n")
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
