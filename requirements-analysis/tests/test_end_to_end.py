"""End-to-end pipeline test against the real corpus; skipped if docs/ is missing."""
from __future__ import annotations

from pathlib import Path

import pytest

from extractors.regex import RegexExtractor
from lib import canonicalise as cm
from lib import coverage as cov
from lib import ingest as ing
from lib import partition as pm
from lib import vocabulary as vm

DOCS = Path(__file__).resolve().parent.parent / "docs"


@pytest.mark.skipif(not DOCS.exists(), reason="docs/ corpus missing")
def test_full_pipeline_runs_on_real_corpus():
    vocab = vm.load()
    extractor = RegexExtractor()
    manifest = ing.default_corpus_manifest(DOCS)

    paragraphs = []
    for entry in manifest:
        if not entry.path.exists():
            pytest.skip(f"missing {entry.path.name}")
        paragraphs.extend(ing.ingest(entry.path, source_access=entry.source_access))

    assert len(paragraphs) > 50, f"only {len(paragraphs)} paragraphs ingested"

    obligations = []
    for p in paragraphs:
        obligations.extend(extractor.extract(p))
    assert len(obligations) > 100, f"only {len(obligations)} obligations extracted"

    para_texts = {p.text for p in paragraphs}
    for o in obligations:
        assert any(o.verbatim in t for t in para_texts), \
            f"verbatim not in any paragraph: {o.verbatim[:80]!r}"

    provisions = pm.partition(cm.canonicalise(obligations, vocab))
    assert len(provisions) > 5

    per = cov.coverage_per_provision(provisions, vocab)
    n_covered = sum(1 for r in per if r["covered"])
    coverage_rate = n_covered / len(per)
    assert coverage_rate >= 0.50, (
        f"only {coverage_rate:.0%} of provisions cover a known artefact — "
        f"the synonym table needs to be extended (run inspection: "
        f"`grep -c Unknown_ sample_results/provisions.csv`)"
    )
