"""Deterministic regex baseline extractor."""
from __future__ import annotations

import re
from typing import List, Sequence

from extractors.base import Extractor, validate_obligation
from lib.types import ExtractedObligation, Paragraph
from lib import vocabulary as vocab_mod


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

_FOOTNOTE_RE = re.compile(r'(?<=[.,;:)])(\d{1,3})(?=[\s.,)]|$)')
_DOUBLE_PUNCT_RE = re.compile(r'([.,;:])\s*\1+')
_WS_RE = re.compile(r'\s+')


def _clean_pdf_text(text: str) -> str:
    """Strip footnote citation markers left by pdfplumber."""
    text = _FOOTNOTE_RE.sub('', text)
    text = _DOUBLE_PUNCT_RE.sub(r'\1', text)
    text = _WS_RE.sub(' ', text).strip()
    return text


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


_CLAUSE_SPLIT_RE = re.compile(r'\s*[,;:—–]\s+|\s*\(\s*|\s*\)\s*')


def _last_clause(text: str) -> str:
    parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(text) if p.strip()]
    return parts[-1] if parts else text.strip()


def _first_clause(text: str) -> str:
    parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(text) if p.strip()]
    return parts[0] if parts else text.strip()


def _build_modal_regex(modals: Sequence[str]) -> re.Pattern:
    if not modals:
        return re.compile(r"$^")
    parts = [re.escape(m) for m in sorted(modals, key=len, reverse=True)]
    return re.compile(r"\b(" + "|".join(parts) + r")\b", re.IGNORECASE)


def _around_modal(sentence: str, m: re.Match) -> tuple[str, str, str]:
    before = sentence[: m.start()].strip(" ,;.")
    modal = m.group(0)
    after = sentence[m.end() :].strip(" ,;.")
    return before, modal, after


def _longest_predicate_prefix(obligation_side: str,
                              predicate_synonyms: list[str]) -> tuple[str, str]:
    s = obligation_side.lstrip()
    for aux in ("not ", "be ", "have "):
        if s.lower().startswith(aux):
            s = s[len(aux):]
    s_lc = s.lower()
    for syn in predicate_synonyms:
        if s_lc.startswith(syn):
            end = len(syn)
            if end < len(s_lc) and s_lc[end].isalpha():
                continue
            artefact = s[end:].strip(" ,.;:")
            if artefact:
                return syn, artefact
    return "", ""


DEFAULT_TIERS = ("Mandatory",)


class RegexExtractor:
    def __init__(self, tiers: Sequence[str] = DEFAULT_TIERS) -> None:
        self.tiers = tuple(tiers)
        v = vocab_mod.load()
        self._predicate_synonyms = sorted(
            (phrase for (slot, phrase), _canon in v.synonyms.items() if slot == "predicate"),
            key=len,
            reverse=True,
        )
        self._modal_phrases = v.modals_for_tiers(self.tiers)
        self._modal_re = _build_modal_regex(self._modal_phrases)
        self.name = "regex-baseline-v2[" + "+".join(self.tiers) + "]"

    def extract(self, p: Paragraph) -> list[ExtractedObligation]:
        out: list[ExtractedObligation] = []
        for sent in _split_sentences(p.text):
            for m in self._modal_re.finditer(sent):
                bearer, modal, obligation_side = _around_modal(sent, m)
                if not bearer:
                    continue
                predicate, artefact = _longest_predicate_prefix(
                    obligation_side, self._predicate_synonyms
                )
                if not predicate or not artefact:
                    continue
                bearer_phrase = _last_clause(_clean_pdf_text(bearer))[-200:]
                artefact_phrase = _first_clause(_clean_pdf_text(artefact))[:200]
                if not bearer_phrase or not artefact_phrase:
                    continue
                row = ExtractedObligation(
                    extractor=self.name,
                    doc_id=p.doc_id,
                    locator=p.locator,
                    verbatim=sent,
                    modal=modal.lower(),
                    bearer_phrase=bearer_phrase,
                    predicate_phrase=predicate.lower(),
                    artefact_phrase=artefact_phrase,
                )
                validate_obligation(row, p)
                out.append(row)
        return out
