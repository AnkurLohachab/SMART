"""Document ingestion: PDF/HTML into an ordered list of Paragraphs."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .types import Paragraph

_MODAL_RE = re.compile(
    r"\b("
    r"shall(?:\s+not)?|"
    r"must(?:\s+not)?|"
    r"should(?:\s+not)?|"
    r"may(?:\s+not)?|"
    r"is\s+required\s+to|are\s+required\s+to|"
    r"is\s+recommended\s+to|"
    r"we\s+recommend|"
    r"recommended"
    r")\b",
    re.IGNORECASE,
)


def doc_id_from_path(p: Path) -> str:
    return p.stem.lower()


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _split_paragraphs(text: str) -> list[str]:
    raw = re.split(r"\n\s*\n", text)
    out = []
    for r in raw:
        cleaned = re.sub(r"\s+", " ", r).strip()
        if cleaned:
            out.append(cleaned)
    return out


def ingest_pdf(path: Path, source_access: str = "full") -> Iterator[Paragraph]:
    import pdfplumber

    doc_id = doc_id_from_path(path)
    with pdfplumber.open(str(path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            for para_idx, para in enumerate(_split_paragraphs(page_text), start=1):
                if not _MODAL_RE.search(para):
                    continue
                yield Paragraph(
                    doc_id=doc_id,
                    locator=f"p.{page_idx} ¶{para_idx}",
                    text=para,
                    source_access=source_access,
                )


def ingest_html(path: Path, source_access: str = "full") -> Iterator[Paragraph]:
    from bs4 import BeautifulSoup

    doc_id = doc_id_from_path(path)
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    for para_idx, para in enumerate(_split_paragraphs(text), start=1):
        if not _MODAL_RE.search(para):
            continue
        yield Paragraph(
            doc_id=doc_id,
            locator=f"p.{para_idx}",
            text=para,
            source_access=source_access,
        )


def ingest(path: Path, source_access: str = "full") -> list[Paragraph]:
    """Route by extension and collect to a list."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return list(ingest_pdf(path, source_access=source_access))
    if suffix in (".html", ".htm"):
        return list(ingest_html(path, source_access=source_access))
    raise ValueError(f"unsupported document type: {suffix} ({path})")



@dataclass(frozen=True)
class CorpusEntry:
    path: Path
    source_access: str


def default_corpus_manifest(docs_dir: Path) -> list[CorpusEntry]:
    """Pinned list of source files, in fixed order."""
    return [
        CorpusEntry(docs_dir / "eu_ai_act_2024_1689.pdf",        "full"),
        CorpusEntry(docs_dir / "eu_mdr_2017_745.pdf",            "full"),
        CorpusEntry(docs_dir / "fda_ai_ml_action_plan_2021.pdf", "full"),
        CorpusEntry(docs_dir / "fda_pccp_guidance_2024.pdf",     "full"),
        CorpusEntry(docs_dir / "fda_lifecycle_draft_2025.pdf",   "full"),
        CorpusEntry(docs_dir / "tripod_ai_2024.pdf",             "full"),
        CorpusEntry(docs_dir / "iso_29119_11_2020_landing.html", "TOC_only"),
        CorpusEntry(docs_dir / "iso_24028_2020_landing.html",    "TOC_only"),
    ]
