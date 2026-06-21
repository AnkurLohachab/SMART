"""Live-API integration test for OpenRouterExtractor; skipped unless OPENROUTER_API_KEY is set."""
from __future__ import annotations

import os

import pytest

from extractors.openrouter import OpenRouterExtractor
from lib.types import Paragraph


pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set",
)


def test_live_smoke():
    """Hit the real API with one paragraph and confirm the wire format works."""
    p = Paragraph(
        doc_id="live_smoke",
        locator="¶1",
        text="Providers of high-risk AI systems shall draw up technical documentation.",
        source_access="full",
    )
    e = OpenRouterExtractor(model="openai/gpt-oss-120b:free")
    rows = e.extract(p)
    assert 0 <= len(rows) <= 2
    for r in rows:
        assert r.verbatim in p.text
        assert r.modal in ("shall", "must")
