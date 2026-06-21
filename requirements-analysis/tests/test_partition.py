"""Partition and equivalence-relation property tests."""
from __future__ import annotations

import pytest

from lib import canonicalise as cm
from lib import partition as pm
from lib import vocabulary as vm
from lib.types import CanonicalProvision, ExtractedObligation


def _cp(b, p, a, src=("d", "¶")) -> CanonicalProvision:
    return CanonicalProvision(
        bearer=b, predicate=p, artefact=a,
        sources=(src,), verbatims=("v",), extractors=("e",),
    )


def test_partition_dedupes_already_unique_input():
    rs = [_cp("Provider", "Produce", "TechnicalDocumentation"),
          _cp("Provider", "Monitor", "PostMarketMonitoringReport")]
    out = pm.partition(rs)
    assert len(out) == 2


def test_partition_raises_on_duplicate_triple():
    rs = [_cp("Provider", "Produce", "TechnicalDocumentation"),
          _cp("Provider", "Produce", "TechnicalDocumentation")]
    with pytest.raises(ValueError, match="partition invariant broken"):
        pm.partition(rs)


def test_partition_output_is_sorted():
    rs = [_cp("Provider", "Produce", "TechnicalDocumentation"),
          _cp("Manufacturer", "Monitor", "PostMarketMonitoringReport")]
    out = pm.partition(rs)
    assert out[0].triple == ("Manufacturer", "Monitor", "PostMarketMonitoringReport")


def test_equivalence_relation_properties():
    triples = [
        ("Provider", "Produce", "TechnicalDocumentation"),
        ("Manufacturer", "Monitor", "PostMarketMonitoringReport"),
        ("Provider", "Produce", "TechnicalDocumentation"),
    ]
    assert pm.equivalence_relation_holds(triples)


def test_partition_count_invariant_under_input_shuffle():
    """N is a function of the input set, not its order."""
    v = vm.load()
    base = [
        ExtractedObligation(extractor="t", doc_id="d", locator="¶1",
                            verbatim="v", modal="shall",
                            bearer_phrase="provider", predicate_phrase="draw up",
                            artefact_phrase="technical documentation"),
        ExtractedObligation(extractor="t", doc_id="d", locator="¶2",
                            verbatim="v", modal="shall",
                            bearer_phrase="manufacturer", predicate_phrase="monitor",
                            artefact_phrase="post-market surveillance"),
    ]
    a = pm.partition(cm.canonicalise(base, v))
    b = pm.partition(cm.canonicalise(list(reversed(base)), v))
    assert len(a) == len(b)
    assert {r.triple for r in a} == {r.triple for r in b}
