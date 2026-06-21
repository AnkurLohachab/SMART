"""Extractor protocol."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from lib.types import ExtractedObligation, Paragraph


@runtime_checkable
class Extractor(Protocol):
    name: str

    def extract(self, p: Paragraph) -> list[ExtractedObligation]:
        ...


def validate_obligation(o: ExtractedObligation, p: Paragraph) -> None:
    if o.doc_id != p.doc_id:
        raise ValueError(f"doc_id mismatch: {o.doc_id} != {p.doc_id}")
    if o.locator != p.locator:
        raise ValueError(f"locator mismatch: {o.locator} != {p.locator}")
    from lib import vocabulary as _vocab_mod
    _v = _vocab_mod.load()
    if " ".join(o.modal.lower().split()) not in _v.modal_tiers:
        raise ValueError(f"unsupported modal (not in modal_tiers.csv): {o.modal!r}")
    if o.verbatim not in p.text:
        raise ValueError(
            f"verbatim not in source paragraph "
            f"(extractor={o.extractor}, doc={o.doc_id}@{o.locator}): "
            f"verbatim={o.verbatim[:80]!r} not substring of {p.text[:80]!r}"
        )
    if not o.bearer_phrase.strip() or not o.predicate_phrase.strip() or not o.artefact_phrase.strip():
        raise ValueError("bearer/predicate/artefact phrases must be non-empty")
