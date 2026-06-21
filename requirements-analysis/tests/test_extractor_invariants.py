"""Extractor invariants: anti-hallucination, modal-only, doc-id integrity."""
from __future__ import annotations

import pytest

from extractors.base import Extractor, validate_obligation
from extractors.regex import RegexExtractor
from lib.types import ExtractedObligation, Paragraph


@pytest.fixture(scope="module")
def extractor() -> Extractor:
    return RegexExtractor()


def _para(text: str) -> Paragraph:
    return Paragraph(doc_id="test", locator="¶1", text=text, source_access="full")


def test_protocol_satisfied(extractor):
    assert isinstance(extractor, Extractor)


def test_emits_for_shall_clause(extractor):
    p = _para("Providers of high-risk AI systems shall draw up technical documentation.")
    rows = extractor.extract(p)
    assert len(rows) == 1
    assert rows[0].modal == "shall"


def test_emits_for_must_clause(extractor):
    p = _para("The manufacturer must monitor the system in deployment.")
    rows = extractor.extract(p)
    assert len(rows) == 1
    assert rows[0].modal == "must"


def test_default_extractor_drops_should_and_may(extractor):
    """Default tier is Mandatory, so should/may are filtered out."""
    p = _para("The provider should consider risk; the deployer may opt out.")
    rows = extractor.extract(p)
    assert rows == []


def test_extractor_at_recommended_tier_accepts_should():
    from extractors.regex import RegexExtractor
    rec_extractor = RegexExtractor(tiers=("Mandatory", "Recommended"))
    p = _para("The provider should produce technical documentation.")
    rows = rec_extractor.extract(p)
    assert len(rows) == 1
    assert rows[0].modal == "should"


def test_two_sentences_two_emissions(extractor):
    p = _para(
        "Providers shall draw up technical documentation. "
        "The manufacturer must monitor the system."
    )
    rows = extractor.extract(p)
    assert len(rows) == 2


def test_verbatim_is_substring_of_paragraph(extractor):
    p = _para("Providers shall draw up technical documentation. Deployers should opt in.")
    for o in extractor.extract(p):
        assert o.verbatim in p.text


def test_doc_id_and_locator_propagate(extractor):
    p = Paragraph(doc_id="my_doc", locator="Art. 99(7)",
                  text="The sponsor shall produce a test protocol.",
                  source_access="full")
    rows = extractor.extract(p)
    assert rows
    for o in rows:
        assert o.doc_id == "my_doc"
        assert o.locator == "Art. 99(7)"


def test_validate_obligation_rejects_hallucination():
    p = _para("The provider shall produce documentation.")
    bad = ExtractedObligation(
        extractor="bad",
        doc_id=p.doc_id,
        locator=p.locator,
        verbatim="THIS TEXT WAS NOT IN THE PARAGRAPH",
        modal="shall",
        bearer_phrase="provider",
        predicate_phrase="produce",
        artefact_phrase="documentation",
    )
    with pytest.raises(ValueError, match="verbatim not in source paragraph"):
        validate_obligation(bad, p)


def test_validate_obligation_rejects_unsupported_modal():
    """An invented modal not in modal_tiers.csv must be rejected."""
    p = _para("The provider should produce documentation.")
    bad = ExtractedObligation(
        extractor="bad", doc_id=p.doc_id, locator=p.locator,
        verbatim=p.text, modal="moonwalk",
        bearer_phrase="provider", predicate_phrase="produce", artefact_phrase="documentation",
    )
    with pytest.raises(ValueError, match="unsupported modal"):
        validate_obligation(bad, p)


def test_validate_obligation_accepts_recommended_tier_modal():
    p = _para("Providers should produce technical documentation.")
    rec = ExtractedObligation(
        extractor="ok", doc_id=p.doc_id, locator=p.locator,
        verbatim=p.text, modal="should",
        bearer_phrase="providers", predicate_phrase="produce",
        artefact_phrase="technical documentation",
    )
    validate_obligation(rec, p)


def test_validate_obligation_rejects_doc_id_mismatch():
    p = _para("The provider shall produce documentation.")
    bad = ExtractedObligation(
        extractor="bad", doc_id="OTHER_DOC", locator=p.locator,
        verbatim=p.text, modal="shall",
        bearer_phrase="provider", predicate_phrase="produce", artefact_phrase="documentation",
    )
    with pytest.raises(ValueError, match="doc_id mismatch"):
        validate_obligation(bad, p)


def test_no_emit_when_only_modal_no_bearer(extractor):
    """A modal with no preceding subject yields no bearer, so nothing is emitted."""
    p = _para("Shall be assessed.")
    assert extractor.extract(p) == []


def test_extractor_is_deterministic(extractor):
    """Same paragraph in, same output out, twice."""
    p = _para(
        "Providers shall draw up technical documentation. "
        "The manufacturer must monitor the system."
    )
    a = extractor.extract(p)
    b = extractor.extract(p)
    def k(o): return (o.modal, o.bearer_phrase, o.predicate_phrase, o.artefact_phrase, o.verbatim)
    assert sorted(map(k, a)) == sorted(map(k, b))
