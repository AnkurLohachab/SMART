"""Pydantic models passed between pipeline stages."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Paragraph(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    locator: str
    text: str
    source_access: str = "full"


class ExtractedObligation(BaseModel):
    model_config = ConfigDict(frozen=True)

    extractor: str
    doc_id: str
    locator: str
    verbatim: str
    modal: str
    bearer_phrase: str
    predicate_phrase: str
    artefact_phrase: str


class CanonicalProvision(BaseModel):
    model_config = ConfigDict(frozen=True)

    bearer: str
    predicate: str
    artefact: str
    sources: tuple[tuple[str, str], ...]
    verbatims: tuple[str, ...]
    extractors: tuple[str, ...]
    oov_terms: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.bearer, self.predicate, self.artefact)
