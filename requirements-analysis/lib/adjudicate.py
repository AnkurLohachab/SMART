"""Two-layer adjudication: formal-logic equivalence plus an LLM-judge panel."""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from lib import canonicalise as canon_mod
from lib import llm_judge as judge_mod
from lib import subsumption as sub
from lib.types import CanonicalProvision, ExtractedObligation, Paragraph

logger = logging.getLogger(__name__)
OUT = Path(__file__).resolve().parent.parent / "sample_results"


def _key(o: ExtractedObligation) -> tuple[str, str]:
    return (o.doc_id, o.locator)


def _to_canonical(extractions: list[ExtractedObligation], vocab) -> list[CanonicalProvision]:
    return canon_mod.canonicalise(extractions, vocab)


def _build_paragraph_lookup(paragraphs: Iterable[Paragraph]) -> dict[tuple[str, str], Paragraph]:
    return {(p.doc_id, p.locator): p for p in paragraphs}


def adjudicate(
    extractions_by_extractor: dict[str, list[ExtractedObligation]],
    paragraphs: list[Paragraph],
    vocab,
    *,
    enable_llm_judge: bool = True,
    max_judge_calls: int = 200,
) -> dict:
    para_lookup = _build_paragraph_lookup(paragraphs)
    extractor_names = list(extractions_by_extractor.keys())

    per_ext_index: dict[str, dict[tuple[str, str], set[tuple]]] = {}
    for name, ext_rows in extractions_by_extractor.items():
        idx: dict[tuple[str, str], set[tuple]] = defaultdict(set)
        for r in ext_rows:
            b, p, a, _oov = canon_mod.canonicalise_one(r, vocab)
            if b.startswith("Unknown_") or p.startswith("Unknown_") or a.startswith("Unknown_"):
                continue
            idx[_key(r)].add((b, p, a))
        per_ext_index[name] = idx

    silver: set[tuple[tuple[str, str], tuple[str, str, str]]] = set()
    judge_log: list[dict] = []
    judge_calls = 0

    all_locators = sorted({loc for idx in per_ext_index.values() for loc in idx})

    for loc in all_locators:
        per_ext_at_loc = {n: per_ext_index[n].get(loc, set()) for n in extractor_names}

        triple_to_voters: dict[tuple, set[str]] = defaultdict(set)
        for ext, triples in per_ext_at_loc.items():
            for t in triples:
                triple_to_voters[t].add(ext)
        for t, voters in triple_to_voters.items():
            if len(voters) >= 2:
                silver.add((loc, t))

        all_triples_here = list(triple_to_voters.keys())
        for t in all_triples_here:
            for u in all_triples_here:
                if t == u:
                    continue
                cp_t = CanonicalProvision(bearer=t[0], predicate=t[1], artefact=t[2],
                                          sources=((loc[0], loc[1]),), verbatims=("",), extractors=())
                cp_u = CanonicalProvision(bearer=u[0], predicate=u[1], artefact=u[2],
                                          sources=((loc[0], loc[1]),), verbatims=("",), extractors=())
                if sub.formally_subsumed(cp_t, cp_u):
                    silver.add((loc, t))
                    silver.add((loc, u))

        if not enable_llm_judge or judge_calls >= max_judge_calls:
            continue
        para = para_lookup.get(loc)
        if para is None:
            continue
        for t, voters in triple_to_voters.items():
            if (loc, t) in silver:
                continue
            if len(voters) != 1:
                continue
            voter = next(iter(voters))
            others = [n for n in extractor_names if n != voter]
            for o in others:
                if judge_calls >= max_judge_calls:
                    break
                other_triples = per_ext_at_loc.get(o, set())
                best = next(iter(other_triples), None)
                tuple_a = f"({t[0]}, {t[1]}, {t[2]})"
                tuple_b = f"({best[0]}, {best[1]}, {best[2]})" if best else "<no extraction>"
                panel = judge_mod.judge_panel(para.text, tuple_a, tuple_b)
                judge_calls += 1
                judge_log.append({
                    "locator": list(loc),
                    "tuple_A": tuple_a, "tuple_A_voter": voter,
                    "tuple_B": tuple_b, "tuple_B_voter": o,
                    "panel": panel,
                })
                if panel["majority_verdict"] in ("same", "partial-overlap"):
                    silver.add((loc, t))

    per_ext_metrics: dict[str, dict] = {}
    silver_locators_triples: dict[tuple[str, str], set[tuple]] = defaultdict(set)
    for (loc, t) in silver:
        silver_locators_triples[loc].add(t)

    for name, idx in per_ext_index.items():
        tp = fp = 0
        for loc, triples in idx.items():
            for t in triples:
                if t in silver_locators_triples.get(loc, set()):
                    tp += 1
                else:
                    fp += 1
        n_silver = sum(len(v) for v in silver_locators_triples.values())
        n_silver_at_seen = sum(
            len(silver_locators_triples.get(loc, set()))
            for loc in idx.keys()
        )
        fn = max(0, n_silver_at_seen - tp)
        per_ext_metrics[name] = {
            "n_extracted": tp + fp,
            "tp": tp, "fp": fp, "fn": fn,
            "precision": (tp / (tp + fp)) if (tp + fp) else None,
            "recall": (tp / (tp + fn)) if (tp + fn) else None,
            "n_silver_at_locators_visited": n_silver_at_seen,
        }

    return {
        "n_silver": sum(len(v) for v in silver_locators_triples.values()),
        "n_judge_calls": judge_calls,
        "per_extractor": per_ext_metrics,
        "judge_log_size": len(judge_log),
    }, judge_log


def write(result: dict, judge_log: list, dst_dir: Path = OUT) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    p = dst_dir / "adjudication.json"
    p.write_text(json.dumps(result, indent=2))
    log_p = dst_dir / "judge_log.json"
    log_p.write_text(json.dumps(judge_log, indent=2))
    return p
