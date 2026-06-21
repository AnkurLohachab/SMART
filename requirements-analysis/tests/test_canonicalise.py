"""Canonicalisation tests."""
from __future__ import annotations

from lib import canonicalise as cm
from lib import vocabulary as vm
from lib.types import ExtractedObligation, Paragraph


def _ob(b="provider", p="draw up", a="technical documentation",
        verbatim="X", doc_id="d", loc="¶1", extractor="regex-baseline-v1"):
    return ExtractedObligation(
        extractor=extractor, doc_id=doc_id, locator=loc,
        verbatim=verbatim, modal="shall",
        bearer_phrase=b, predicate_phrase=p, artefact_phrase=a,
    )


def test_basic_canonicalisation():
    v = vm.load()
    rows = cm.canonicalise([_ob()], v)
    assert len(rows) == 1
    assert rows[0].triple == ("Provider", "Produce", "TechnicalDocumentation")
    assert rows[0].oov_terms == ()


def test_longest_match_rescues_phrase_with_adjective():
    v = vm.load()
    rows = cm.canonicalise([_ob(a="comprehensive technical documentation")], v)
    assert rows[0].artefact == "TechnicalDocumentation"


def test_oov_term_is_flagged():
    v = vm.load()
    rows = cm.canonicalise([_ob(a="moon dust")], v)
    assert len(rows) == 1
    assert rows[0].artefact == "Unknown_Artefact"
    assert any("moon dust" in t for t in rows[0].oov_terms)


def test_idempotence():
    """Re-canonicalising duplicated input keeps N and triples stable."""
    v = vm.load()
    obs = [
        _ob(b="provider", p="draw up", a="technical documentation"),
        _ob(b="manufacturer", p="monitor", a="post-market surveillance"),
    ]
    a = cm.canonicalise(obs, v)
    b = cm.canonicalise(obs + obs, v)
    assert {r.triple for r in a} == {r.triple for r in b}
    by_triple = {r.triple: r for r in b}
    assert all(len(by_triple[t.triple].sources) >= 1 for t in a)


def test_merge_collapses_same_triple():
    """Same canonical triple from different sources merges, keeping both sources."""
    v = vm.load()
    obs = [
        _ob(b="provider", p="draw up", a="technical documentation",
            doc_id="eu_ai_act", loc="Art. 11"),
        _ob(b="manufacturer", p="prepare", a="technical documentation",
            doc_id="eu_mdr",     loc="Art. 10"),
    ]
    rows = cm.canonicalise(obs, v)
    assert len(rows) == 2
    obs2 = [
        _ob(b="provider", p="draw up",   a="technical documentation",
            doc_id="eu_ai_act", loc="Art. 11"),
        _ob(b="provider", p="prepare",   a="technical documentation",
            doc_id="eu_mdr",     loc="Art. 10"),
    ]
    rows2 = cm.canonicalise(obs2, v)
    assert len(rows2) == 1
    assert rows2[0].triple == ("Provider", "Produce", "TechnicalDocumentation")
    assert {s[0] for s in rows2[0].sources} == {"eu_ai_act", "eu_mdr"}


def test_sources_sorted_and_deduped():
    v = vm.load()
    obs = [
        _ob(doc_id="x", loc="¶1"), _ob(doc_id="x", loc="¶1"),
        _ob(doc_id="x", loc="¶2"),
    ]
    rows = cm.canonicalise(obs, v)
    assert rows[0].sources == (("x", "¶1"), ("x", "¶2"))


def test_sources_and_verbatims_are_row_aligned():
    """sources[i] and verbatims[i] must describe the same record."""
    v = vm.load()
    obs = [
        _ob(doc_id="lifecycle", loc="p.40 ¶1",
            verbatim="Sponsors should provide the recommended information"),
        _ob(doc_id="lifecycle", loc="p.40 ¶1",
            verbatim="Sponsors should provide the recommended information"),
        _ob(doc_id="pccp", loc="p.19 ¶1",
            verbatim="The PCCP should be described in publicly available device summaries"),
    ]
    rows = cm.canonicalise(obs, v)
    assert len(rows) >= 1
    target = rows[0]
    assert len(target.sources) == len(target.verbatims), \
        f"row alignment broken: {len(target.sources)} sources vs {len(target.verbatims)} verbatims"
    pairs = set(zip(target.sources, target.verbatims))
    assert (("lifecycle", "p.40 ¶1"),
            "Sponsors should provide the recommended information") in pairs
    assert (("pccp", "p.19 ¶1"),
            "The PCCP should be described in publicly available device summaries") in pairs
    by_source = dict(zip(target.sources, target.verbatims))
    assert "PCCP" in by_source[("pccp", "p.19 ¶1")], \
        ("verbatim under pccp/p.19 ¶1 should mention PCCP, got: "
         f"{by_source[('pccp','p.19 ¶1')]!r}")
