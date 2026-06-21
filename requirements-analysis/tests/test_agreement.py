"""Cohen's κ on equivalence-class membership."""
from __future__ import annotations

from lib import agreement as ag
from lib.types import CanonicalProvision


def _cp(b, p, a):
    return CanonicalProvision(
        bearer=b, predicate=p, artefact=a,
        sources=(("d", "¶"),), verbatims=("v",), extractors=("x",),
    )


def test_kappa_perfect_agreement():
    assert ag.cohens_kappa([1, 0, 1, 1], [1, 0, 1, 1]) == 1.0


def test_kappa_complete_disagreement():
    """Half/half opposite — random would give 0."""
    k = ag.cohens_kappa([1, 0, 1, 0], [0, 1, 0, 1])
    assert k <= 0.0


def test_membership_matrix_union_of_triples():
    a = [_cp("Provider", "Produce", "TechnicalDocumentation")]
    b = [_cp("Provider", "Produce", "TechnicalDocumentation"),
         _cp("Manufacturer", "Monitor", "PostMarketMonitoringReport")]
    triples, vec = ag.membership_matrix({"A": a, "B": b})
    assert len(triples) == 2
    assert vec["A"].count(True) == 1
    assert vec["B"].count(True) == 2


def test_pairwise_kappa_returns_one_row_per_pair():
    a = [_cp("Provider", "Produce", "TechnicalDocumentation")]
    b = [_cp("Provider", "Produce", "TechnicalDocumentation")]
    c = [_cp("Manufacturer", "Monitor", "PostMarketMonitoringReport")]
    rows = ag.pairwise_kappa({"A": a, "B": b, "C": c})
    pairs = {(r["extractor_a"], r["extractor_b"]) for r in rows}
    assert len(rows) == 3
    assert ("A", "B") in pairs
    assert ("A", "C") in pairs
    assert ("B", "C") in pairs
