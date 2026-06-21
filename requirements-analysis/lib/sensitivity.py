"""Sensitivity grid runner over extractor, modal tier, and vocab variant."""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from extractors.deepinfra import DeepInfraExtractor
from extractors.openrouter import OpenRouterExtractor
from extractors.regex import RegexExtractor
from lib import agreement as agree_mod
from lib import canonicalise as canon_mod
from lib import coverage as cov_mod
from lib import ingest as ing_mod
from lib import partition as part_mod
from lib import vocabulary as vocab_mod
from lib.types import CanonicalProvision, ExtractedObligation

logger = logging.getLogger(__name__)


HERE = Path(__file__).resolve().parent.parent
DOCS = HERE / "docs"
OUT = HERE / "sample_results"



def _truncate_vocab(v: vocab_mod.Vocabulary, fraction: float = 0.30) -> vocab_mod.Vocabulary:
    """Drop a deterministic hash-keyed fraction of synonym rows."""
    keep = []
    for (slot, phrase), canon in v.synonyms.items():
        h = abs(hash((slot, phrase, "trunc"))) % 100
        if h >= fraction * 100:
            keep.append(((slot, phrase), canon))
    return vocab_mod.Vocabulary(
        bearers=v.bearers, predicates=v.predicates, artefacts=v.artefacts,
        synonyms=dict(keep), coverage=v.coverage, modal_tiers=v.modal_tiers,
    )


def _over_extend_vocab(v: vocab_mod.Vocabulary) -> vocab_mod.Vocabulary:
    """Add deliberately permissive synonyms to test how much N moves."""
    extra = {
        ("artefact", "information"): "TechnicalDocumentation",
        ("artefact", "report"): "TechnicalDocumentation",
        ("artefact", "data"): "DataGovernancePolicy",
        ("artefact", "system"): "TechnicalDocumentation",
        ("artefact", "system shall"): "TechnicalDocumentation",
        ("predicate", "comply"): "Verify",
    }
    new_syn = dict(v.synonyms)
    for k, val in extra.items():
        new_syn[k] = val
    return vocab_mod.Vocabulary(
        bearers=v.bearers, predicates=v.predicates, artefacts=v.artefacts,
        synonyms=new_syn, coverage=v.coverage, modal_tiers=v.modal_tiers,
    )


VOCAB_VARIANTS: dict[str, Callable[[vocab_mod.Vocabulary], vocab_mod.Vocabulary]] = {
    "curated":      lambda v: v,
    "truncated30":  lambda v: _truncate_vocab(v, 0.30),
    "overextended": _over_extend_vocab,
}



TIER_SETS = {
    "M":   ("Mandatory",),
    "M+R": ("Mandatory", "Recommended"),
    "M+R+P": ("Mandatory", "Recommended", "Permitted"),
}



@dataclass
class ExtractorSpec:
    name: str
    constructor: Callable


def _free_models() -> list[str]:
    raw = os.environ.get("OPENROUTER_MODELS", "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _paid_models() -> list[str]:
    raw = os.environ.get("DEEPINFRA_MODELS", "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def regex_extractor_specs(tiers: tuple[str, ...]) -> list[ExtractorSpec]:
    return [ExtractorSpec(
        name=f"regex[{'+'.join(tiers)}]",
        constructor=lambda t=tiers: RegexExtractor(tiers=t),
    )]


def llm_extractor_specs() -> list[ExtractorSpec]:
    """DeepInfra when DEEPINFRA_API_KEY is set, else OpenRouter fallback."""
    out = []
    if os.environ.get("DEEPINFRA_API_KEY"):
        for m in _paid_models():
            out.append(ExtractorSpec(
                name=f"llm[{m}]",
                constructor=lambda model=m: DeepInfraExtractor(model=model),
            ))
    if os.environ.get("OPENROUTER_API_KEY") and not out:
        for m in _free_models():
            out.append(ExtractorSpec(
                name=f"llm[{m}]",
                constructor=lambda model=m: OpenRouterExtractor(model=model),
            ))
    return out



def _ingest_corpus() -> list:
    paragraphs = []
    for entry in ing_mod.default_corpus_manifest(DOCS):
        if entry.path.exists():
            paragraphs.extend(ing_mod.ingest(entry.path,
                                             source_access=entry.source_access))
    return paragraphs


def run_cell(extractor, vocab, paragraphs) -> dict:
    obligations: list[ExtractedObligation] = []
    for p in paragraphs:
        obligations.extend(extractor.extract(p))
    provisions = part_mod.partition(canon_mod.canonicalise(obligations, vocab))
    n = len(provisions)
    n_oov = sum(1 for r in provisions if r.oov_terms)
    per_cov = cov_mod.coverage_per_provision(provisions, vocab)
    n_cov = sum(1 for r in per_cov if r["covered"])
    return {
        "extractor": extractor.name,
        "n_raw": len(obligations),
        "N": n,
        "n_oov": n_oov,
        "n_covered": n_cov,
        "provisions": provisions,
    }


def run_grid() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    paragraphs = _ingest_corpus()
    base_vocab = vocab_mod.load()

    grid_rows: list[dict] = []
    canonical_per_extractor: dict[str, list[CanonicalProvision]] = {}

    print(f"# regex grid: 3 tiers × 3 vocab variants × 1 extractor = 9 cells")
    for tier_label, tiers in TIER_SETS.items():
        for spec in regex_extractor_specs(tiers):
            extractor = spec.constructor()
            for vocab_label, vocab_fn in VOCAB_VARIANTS.items():
                vocab = vocab_fn(base_vocab)
                cell = run_cell(extractor, vocab, paragraphs)
                grid_rows.append({
                    "tier": tier_label,
                    "extractor": cell["extractor"],
                    "vocab_variant": vocab_label,
                    "n_raw": cell["n_raw"],
                    "N": cell["N"],
                    "n_oov": cell["n_oov"],
                    "n_covered": cell["n_covered"],
                })
                if tier_label == "M" and vocab_label == "curated":
                    canonical_per_extractor[cell["extractor"]] = cell["provisions"]

    llm_specs = llm_extractor_specs()
    if llm_specs:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        canonical_vocab = base_vocab
        print(f"# LLM grid: 1 cell (M / curated) × {len(llm_specs)} models, "
              f"full {len(paragraphs)}-paragraph corpus, parallel")

        def _llm_run(spec):
            print(f"  start {spec.name}")
            extractor = spec.constructor()
            cell = run_cell(extractor, canonical_vocab, paragraphs)
            print(f"  done {spec.name}: N={cell['N']} raw={cell['n_raw']}")
            return spec.name, cell

        with ThreadPoolExecutor(max_workers=len(llm_specs)) as ex:
            futures = [ex.submit(_llm_run, spec) for spec in llm_specs]
            for fut in as_completed(futures):
                spec_name, cell = fut.result()
                grid_rows.append({
                    "tier": "M",
                    "extractor": cell["extractor"],
                    "vocab_variant": "curated",
                    "n_raw": cell["n_raw"],
                    "N": cell["N"],
                    "n_oov": cell["n_oov"],
                    "n_covered": cell["n_covered"],
                })
                canonical_per_extractor[cell["extractor"]] = cell["provisions"]

    grid_csv = OUT / "sensitivity_grid.csv"
    with grid_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(grid_rows[0].keys()))
        w.writeheader()
        for row in grid_rows:
            w.writerow(row)

    agreement_rows = agree_mod.pairwise_kappa(canonical_per_extractor)
    agreement_csv = OUT / "agreement_matrix.csv"
    if agreement_rows:
        with agreement_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(agreement_rows[0].keys()))
            w.writeheader()
            for row in agreement_rows:
                w.writerow(row)

    return {
        "grid_csv": str(grid_csv),
        "agreement_csv": str(agreement_csv),
        "n_cells": len(grid_rows),
        "n_pairs": len(agreement_rows),
    }


if __name__ == "__main__":
    summary = run_grid()
    print("# sensitivity grid")
    for k, v in summary.items():
        print(f"  {k}: {v}")
