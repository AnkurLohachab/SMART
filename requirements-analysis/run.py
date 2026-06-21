"""End-to-end pipeline runner. Outputs land under sample_results/."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from extractors.regex import RegexExtractor
from lib import canonicalise as canon_mod
from lib import coverage as cov_mod
from lib import ingest as ing
from lib import partition as part_mod
from lib import vocabulary as vocab_mod
from lib.types import ExtractedObligation, Paragraph

HERE = Path(__file__).resolve().parent
DOCS = HERE / "docs"
OUT = HERE / "sample_results"
EXTRACTIONS = HERE / "extractions"

EXTRACTORS = {
    "regex": lambda: __import__("extractors.regex", fromlist=["RegexExtractor"]).RegexExtractor(tiers=("Mandatory", "Recommended")),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", default="regex", choices=sorted(EXTRACTORS))
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    extractor = EXTRACTORS[args.extractor]()
    vocab = vocab_mod.load()
    manifest = ing.default_corpus_manifest(DOCS)

    print(f"# requirements-analysis pipeline")
    print(f"  extractor : {extractor.name}")
    print(f"  corpus    : {len(manifest)} docs at {DOCS}")

    all_paragraphs: list[Paragraph] = []
    per_doc_counts = []
    for entry in manifest:
        if not entry.path.exists():
            print(f"  ! missing source: {entry.path.name} — skipped")
            continue
        sha = ing.file_sha256(entry.path)
        paras = ing.ingest(entry.path, source_access=entry.source_access)
        all_paragraphs.extend(paras)
        per_doc_counts.append((entry.path.name, sha[:12], len(paras)))
        print(f"    {entry.path.name:42s} sha={sha[:12]} paras={len(paras)}")

    obligations: list[ExtractedObligation] = []
    for p in all_paragraphs:
        obligations.extend(extractor.extract(p))
    print(f"  extracted : {len(obligations)} raw obligations")

    provisions = canon_mod.canonicalise(obligations, vocab)
    provisions = part_mod.partition(provisions)
    n = len(provisions)
    n_oov = sum(1 for r in provisions if r.oov_terms)
    print(f"  partitioned: N = {n} equivalence classes ({n_oov} contain OOV terms)")

    per_prov = cov_mod.coverage_per_provision(provisions, vocab)
    grouped = cov_mod.grouped_for_paper(provisions, vocab)
    n_covered = sum(1 for r in per_prov if r["covered"])
    print(f"  coverage  : {n_covered}/{n} provisions map to a SMART artefact")

    if args.no_write:
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    EXTRACTIONS.mkdir(parents=True, exist_ok=True)

    by_doc: dict[str, list] = {}
    for o in obligations:
        by_doc.setdefault(o.doc_id, []).append(o.model_dump())
    ext_dir = EXTRACTIONS / extractor.name
    ext_dir.mkdir(parents=True, exist_ok=True)
    for doc_id, rows in by_doc.items():
        (ext_dir / f"{doc_id}.json").write_text(json.dumps(rows, indent=2))

    with (OUT / "provisions.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_prov[0].keys()) if per_prov else
                           ["bearer", "predicate", "artefact", "n_sources",
                            "covered", "smart_section", "smart_component",
                            "extractors"])
        w.writeheader()
        for r in per_prov:
            w.writerow(r)

    with (OUT / "coverage_table.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(grouped[0].keys()) if grouped else
                           ["artefact", "smart_section", "smart_component",
                            "sources", "n_provisions", "note"])
        w.writeheader()
        for r in grouped:
            w.writerow(r)

    partition_dump = [
        {
            "bearer": r.bearer,
            "predicate": r.predicate,
            "artefact": r.artefact,
            "sources": list(r.sources),
            "verbatims": list(r.verbatims),
            "extractors": list(r.extractors),
            "oov_terms": list(r.oov_terms),
        }
        for r in provisions
    ]
    (OUT / "partition.json").write_text(json.dumps(partition_dump, indent=2))

    rep = [
        f"# requirements-analysis report — {datetime.now(timezone.utc).isoformat()}",
        "",
        f"- Extractor: `{extractor.name}`",
        f"- Corpus: {len(manifest)} sources",
        f"- Raw obligations extracted: **{len(obligations)}**",
        f"- Equivalence classes (N): **{n}**",
        f"- Provisions covered by SMART: **{n_covered} / {n}**",
        f"- Provisions containing OOV terms: **{n_oov}**",
        "",
        "## Per-document",
        "",
        "| document | sha256 (12) | paragraphs |",
        "|---|---|---|",
    ]
    for name, sha, paras in per_doc_counts:
        rep.append(f"| {name} | `{sha}` | {paras} |")
    rep.extend([
        "",
        "## Source-access caveats",
        "",
        "* **ISO/IEC TR 29119-11:2020** and **ISO/IEC TR 24028:2020** are read",
        "  at TOC-only level (`source_access: TOC_only`). The publicly-available",
        "  iso.org landing pages contain abstract + scope statements but no",
        "  normative `shall`/`should` text — the ingest therefore correctly",
        "  emits 0 paragraphs from each. The paper's `47 provisions` count",
        "  presumably draws from the paid normative body of these standards;",
        "  the ISO contribution requires institutional access.",
        "* **TRIPOD+AI** uses recommendation phrasing (`should`, `we recommend`)",
        "  that lands in the *Recommended* modal tier, not *Mandatory*. The",
        "  default extractor configuration runs *Mandatory* only — see the",
        "  sensitivity grid for the per-tier breakdown.",
    ])
    (OUT / "report.md").write_text("\n".join(rep))
    print(f"  wrote     : {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
