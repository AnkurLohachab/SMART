"""Tests for the regex extractor text-cleanup helpers."""
from __future__ import annotations

from extractors.regex import (
    _clean_pdf_text, _first_clause, _last_clause, RegexExtractor,
)
from lib.types import Paragraph


def test_clean_pdf_strips_footnote_markers():
    raw = "approval order,63 510(k) summary,64,65 or De Novo decision summary.66"
    cleaned = _clean_pdf_text(raw)
    assert "63" not in cleaned
    assert "64" not in cleaned
    assert "65" not in cleaned
    assert "66" not in cleaned
    assert "approval order" in cleaned
    assert "510(k) summary" in cleaned
    assert "De Novo decision summary" in cleaned


def test_clean_pdf_preserves_real_numbers():
    """Years and counts in prose must not be stripped."""
    raw = "The manufacturer was certified in 2024 and shipped 1500 units."
    cleaned = _clean_pdf_text(raw)
    assert "2024" in cleaned
    assert "1500" in cleaned


def test_clean_pdf_does_not_strip_inline_line_numbers_documented_limitation():
    """Inline margin line numbers are not stripped (overlap with real numbers)."""
    raw = ("Sponsors should provide the recommended information 1503 "
           "excluding any patient identifiers.")
    cleaned = _clean_pdf_text(raw)
    assert "1503" in cleaned


def test_last_clause_returns_subject_after_commas():
    s = ("In cases where Article 5 applies, where conditions referred to in "
         "paragraph 2 are met, the manufacturer")
    assert _last_clause(s) == "the manufacturer"


def test_last_clause_handles_parens():
    assert _last_clause("X (per Article 5) the manufacturer") == "the manufacturer"


def test_first_clause_returns_head_noun():
    assert _first_clause("technical documentation, including all annexes") \
        == "technical documentation"


def test_first_clause_no_punct_returns_input():
    assert _first_clause("technical documentation") == "technical documentation"


def test_extract_produces_tighter_bearer_on_pdf_noise_paragraph():
    """A noisy paragraph yields a clean, short bearer_phrase."""
    text = ("In accordance with Article 5,63 as applicable,64 "
            "the sponsor shall provide technical documentation "
            "including all annexes.")
    p = Paragraph(doc_id="test", locator="p.1 ¶1", text=text)
    ext = RegexExtractor(["Mandatory"])
    rows = ext.extract(p)
    assert rows, "expected at least one extraction"
    r = rows[0]
    assert len(r.bearer_phrase) < 30, \
        f"bearer_phrase too long: {len(r.bearer_phrase)} chars: {r.bearer_phrase!r}"
    assert "sponsor" in r.bearer_phrase.lower()
    for noise in ("63", "64"):
        assert noise not in r.bearer_phrase, \
            f"bearer_phrase still contains footnote {noise!r}: {r.bearer_phrase!r}"
    assert r.artefact_phrase.lower().startswith("technical documentation")
    assert len(r.artefact_phrase) < 80
