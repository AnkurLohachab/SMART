"""OpenRouterExtractor tests using a fake HTTP transport."""
from __future__ import annotations

import json

import pytest

from extractors.openrouter import OpenRouterExtractor
from lib.types import Paragraph


def _fake_http(returns: dict):
    def post(_body):
        return returns
    return post


def _completion(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def _para(text: str) -> Paragraph:
    return Paragraph(doc_id="d", locator="¶1", text=text, source_access="full")


def test_parses_well_formed_json_response():
    p = _para("Providers shall draw up technical documentation.")
    fake_resp = _completion(json.dumps({
        "obligations": [
            {
                "verbatim": "Providers shall draw up technical documentation.",
                "modal": "shall",
                "bearer_phrase": "Providers",
                "predicate_phrase": "draw up",
                "artefact_phrase": "technical documentation",
            }
        ]
    }))
    e = OpenRouterExtractor(model="test/model:free",
                            api_key="dummy", _http=_fake_http(fake_resp))
    rows = e.extract(p)
    assert len(rows) == 1
    assert rows[0].modal == "shall"
    assert rows[0].bearer_phrase == "Providers"
    assert rows[0].extractor == "openrouter[test/model:free]"


def test_anti_hallucination_drops_unverifiable_verbatim():
    """A verbatim not present in the source is dropped."""
    p = _para("Providers shall draw up technical documentation.")
    fake_resp = _completion(json.dumps({
        "obligations": [
            {
                "verbatim": "DEPLOYERS SHALL DELETE EVERYTHING.",
                "modal": "shall",
                "bearer_phrase": "deployers",
                "predicate_phrase": "delete",
                "artefact_phrase": "everything",
            }
        ]
    }))
    e = OpenRouterExtractor(model="test", api_key="dummy", _http=_fake_http(fake_resp))
    assert e.extract(p) == []


def test_drops_rows_with_unknown_modal():
    p = _para("Providers shall draw up documentation.")
    fake_resp = _completion(json.dumps({
        "obligations": [
            {
                "verbatim": "Providers shall draw up documentation.",
                "modal": "moonwalk",
                "bearer_phrase": "Providers",
                "predicate_phrase": "draw up",
                "artefact_phrase": "documentation",
            }
        ]
    }))
    e = OpenRouterExtractor(model="test", api_key="dummy", _http=_fake_http(fake_resp))
    assert e.extract(p) == []


def test_handles_markdown_fenced_json():
    p = _para("The provider shall produce documentation.")
    fake_resp = _completion(
        "Sure! Here you go:\n```json\n"
        + json.dumps({
            "obligations": [{
                "verbatim": "The provider shall produce documentation.",
                "modal": "shall",
                "bearer_phrase": "the provider",
                "predicate_phrase": "produce",
                "artefact_phrase": "documentation",
            }]
        })
        + "\n```\nHope that helps."
    )
    e = OpenRouterExtractor(model="test", api_key="dummy", _http=_fake_http(fake_resp))
    rows = e.extract(p)
    assert len(rows) == 1


def test_empty_obligations_list_is_valid():
    p = _para("This paragraph contains nothing actionable.")
    fake_resp = _completion(json.dumps({"obligations": []}))
    e = OpenRouterExtractor(model="test", api_key="dummy", _http=_fake_http(fake_resp))
    assert e.extract(p) == []


def test_malformed_json_returns_empty():
    p = _para("Providers shall produce documentation.")
    fake_resp = _completion("not json at all, just words")
    e = OpenRouterExtractor(model="test", api_key="dummy", _http=_fake_http(fake_resp))
    assert e.extract(p) == []


def test_http_failure_returns_empty_not_raises():
    def boom(_body):
        raise RuntimeError("simulated 503")
    p = _para("Providers shall produce documentation.")
    e = OpenRouterExtractor(model="test", api_key="dummy", _http=boom)
    assert e.extract(p) == []


def test_constructor_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterExtractor(model="test")
