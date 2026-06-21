"""Negative control: run the pipeline over a non-regulatory corpus; expect n_covered near 0."""
from __future__ import annotations

import logging
from pathlib import Path

from extractors.regex import RegexExtractor
from lib import canonicalise as canon_mod
from lib import coverage as cov_mod
from lib import ingest as ing_mod
from lib import partition as part_mod
from lib import vocabulary as vocab_mod

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent.parent
CONTROL_DIR = HERE / "control_corpus"


def run() -> dict:
    """Run the regex extractor over the negative-control corpus."""
    vocab = vocab_mod.load()
    extractor = RegexExtractor(tiers=("Mandatory",))

    paragraphs = []
    for path in sorted(CONTROL_DIR.glob("*.html")):
        paragraphs.extend(ing_mod.ingest(path))
    for path in sorted(CONTROL_DIR.glob("*.pdf")):
        paragraphs.extend(ing_mod.ingest(path))

    obligations = []
    for p in paragraphs:
        obligations.extend(extractor.extract(p))

    provisions = part_mod.partition(canon_mod.canonicalise(obligations, vocab))
    per_cov = cov_mod.coverage_per_provision(provisions, vocab)

    n = len(provisions)
    n_covered = sum(1 for r in per_cov if r["covered"])
    n_oov = sum(1 for r in provisions if r.oov_terms)
    return {
        "n_paragraphs": len(paragraphs),
        "n_raw_obligations": len(obligations),
        "n_equivalence_classes": n,
        "n_covered": n_covered,
        "n_oov": n_oov,
        "specificity_pass": n_covered <= 1,
    }


if __name__ == "__main__":
    s = run()
    print("# negative control")
    for k, v in s.items():
        print(f"  {k}: {v}")
