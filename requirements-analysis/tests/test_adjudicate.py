"""Adjudicate (D4') unit tests with hand-built fixtures; judge panel stubbed."""
from __future__ import annotations

import pytest

from lib import adjudicate as adj
from lib import llm_judge as judge_mod
from lib.types import ExtractedObligation, Paragraph
from lib.vocabulary import Vocabulary


def _mk_vocab() -> Vocabulary:
    """Tiny closed vocabulary covering only what the fixtures use."""
    bearers = frozenset({"Provider", "Deployer"})
    predicates = frozenset({"draw_up", "monitor"})
    artefacts = frozenset({"TechnicalDocumentation", "PostMarketLog"})
    synonyms: dict[tuple[str, str], str] = {
        ("bearer", "provider"):                          "Provider",
        ("bearer", "providers of high-risk ai systems"): "Provider",
        ("bearer", "deployer"):                          "Deployer",
        ("predicate", "draw up"):                        "draw_up",
        ("predicate", "prepare"):                        "draw_up",
        ("predicate", "monitor"):                        "monitor",
        ("artefact", "technical documentation"):         "TechnicalDocumentation",
        ("artefact", "the technical file"):              "TechnicalDocumentation",
        ("artefact", "post-market log"):                 "PostMarketLog",
    }
    return Vocabulary(
        bearers=bearers,
        predicates=predicates,
        artefacts=artefacts,
        synonyms=synonyms,
        coverage=(),
        modal_tiers={"shall": "Mandatory"},
    )


def _mk_para(doc: str, loc: str, text: str = "fixture text") -> Paragraph:
    return Paragraph(doc_id=doc, locator=loc, text=text)


def _mk_ob(extractor: str, doc: str, loc: str, bearer: str, predicate: str, artefact: str,
           verbatim: str = "fixture") -> ExtractedObligation:
    return ExtractedObligation(
        extractor=extractor, doc_id=doc, locator=loc,
        verbatim=verbatim, modal="shall",
        bearer_phrase=bearer, predicate_phrase=predicate, artefact_phrase=artefact,
    )


def test_two_extractors_agree_yields_silver_and_tp():
    vocab = _mk_vocab()
    para = _mk_para("doc1", "p1")
    A = [_mk_ob("A", "doc1", "p1", "Provider", "draw up", "technical documentation")]
    B = [_mk_ob("B", "doc1", "p1", "providers of high-risk AI systems",
                "prepare", "the technical file")]

    result, _log = adj.adjudicate(
        {"A": A, "B": B}, [para], vocab, enable_llm_judge=False, max_judge_calls=0,
    )
    assert result["n_silver"] == 1
    pa, pb = result["per_extractor"]["A"], result["per_extractor"]["B"]
    assert pa == {"n_extracted": 1, "tp": 1, "fp": 0, "fn": 0,
                  "precision": 1.0, "recall": 1.0, "n_silver_at_locators_visited": 1}
    assert pb == {"n_extracted": 1, "tp": 1, "fp": 0, "fn": 0,
                  "precision": 1.0, "recall": 1.0, "n_silver_at_locators_visited": 1}


def test_judge_says_same_promotes_to_silver(monkeypatch):
    vocab = _mk_vocab()
    para = _mk_para("doc1", "p1")
    A = [_mk_ob("A", "doc1", "p1", "Provider", "draw up", "technical documentation")]
    B: list[ExtractedObligation] = []

    monkeypatch.setattr(judge_mod, "judge_panel",
                        lambda *args, **kw: {"majority_verdict": "same",
                                             "agreement_fraction": 1.0,
                                             "mean_confidence": 1.0,
                                             "n_valid_judges": 2,
                                             "per_model": {}})
    result, _log = adj.adjudicate(
        {"A": A, "B": B}, [para], vocab, enable_llm_judge=True, max_judge_calls=10,
    )
    pa = result["per_extractor"]["A"]
    pb = result["per_extractor"]["B"]
    assert result["n_silver"] == 1
    assert result["n_judge_calls"] == 1
    assert pa["tp"] == 1 and pa["fp"] == 0 and pa["fn"] == 0
    assert pa["precision"] == 1.0 and pa["recall"] == 1.0
    assert pb == {"n_extracted": 0, "tp": 0, "fp": 0, "fn": 0,
                  "precision": None, "recall": None,
                  "n_silver_at_locators_visited": 0}


def test_judge_says_different_keeps_triple_as_fp(monkeypatch):
    vocab = _mk_vocab()
    para = _mk_para("doc1", "p1")
    A = [_mk_ob("A", "doc1", "p1", "Provider", "draw up", "technical documentation")]
    B = [_mk_ob("B", "doc1", "p1", "Deployer", "monitor", "post-market log")]

    monkeypatch.setattr(judge_mod, "judge_panel",
                        lambda *args, **kw: {"majority_verdict": "different",
                                             "agreement_fraction": 1.0,
                                             "mean_confidence": 1.0,
                                             "n_valid_judges": 2,
                                             "per_model": {}})
    result, _log = adj.adjudicate(
        {"A": A, "B": B}, [para], vocab, enable_llm_judge=True, max_judge_calls=10,
    )
    assert result["n_silver"] == 0
    pa = result["per_extractor"]["A"]
    pb = result["per_extractor"]["B"]
    assert pa["tp"] == 0 and pa["fp"] == 1 and pa["fn"] == 0
    assert pb["tp"] == 0 and pb["fp"] == 1 and pb["fn"] == 0
    assert pa["precision"] == 0.0 and pa["recall"] is None
    assert pb["precision"] == 0.0 and pb["recall"] is None


def test_oov_triples_are_skipped():
    """An OOV bearer phrase is flagged Unknown_* and excluded from the index."""
    vocab = _mk_vocab()
    para = _mk_para("doc1", "p1")
    A = [_mk_ob("A", "doc1", "p1", "Notified Body", "draw up", "technical documentation")]
    B = [_mk_ob("B", "doc1", "p1", "Provider", "draw up", "technical documentation")]

    result, _log = adj.adjudicate(
        {"A": A, "B": B}, [para], vocab, enable_llm_judge=False, max_judge_calls=0,
    )
    assert result["n_silver"] == 0
    pa = result["per_extractor"]["A"]
    pb = result["per_extractor"]["B"]
    assert pa["n_extracted"] == 0
    assert pb["tp"] == 0 and pb["fp"] == 1


def test_three_extractors_majority_agreement_makes_silver():
    vocab = _mk_vocab()
    para = _mk_para("doc1", "p1")
    A = [_mk_ob("A", "doc1", "p1", "Provider", "draw up", "technical documentation")]
    B = [_mk_ob("B", "doc1", "p1", "Provider", "prepare", "the technical file")]
    C = [_mk_ob("C", "doc1", "p1", "Deployer", "monitor", "post-market log")]

    result, _log = adj.adjudicate(
        {"A": A, "B": B, "C": C}, [para], vocab,
        enable_llm_judge=False, max_judge_calls=0,
    )
    assert result["n_silver"] == 1
    pa = result["per_extractor"]["A"]
    pb = result["per_extractor"]["B"]
    pc = result["per_extractor"]["C"]
    assert (pa["tp"], pa["fp"]) == (1, 0)
    assert (pb["tp"], pb["fp"]) == (1, 0)
    assert (pc["tp"], pc["fp"]) == (0, 1)


def test_max_judge_calls_cap_respected(monkeypatch):
    vocab = _mk_vocab()
    paras = [_mk_para("doc1", f"p{i}") for i in range(5)]
    A: list[ExtractedObligation] = []
    B: list[ExtractedObligation] = []
    for i, p in enumerate(paras):
        A.append(_mk_ob("A", p.doc_id, p.locator, "Provider", "draw up",
                        "technical documentation"))
        B.append(_mk_ob("B", p.doc_id, p.locator, "Deployer", "monitor",
                        "post-market log"))

    call_counter = {"n": 0}
    def stub_panel(*args, **kw):
        call_counter["n"] += 1
        return {"majority_verdict": "different", "agreement_fraction": 1.0,
                "mean_confidence": 1.0, "n_valid_judges": 2, "per_model": {}}
    monkeypatch.setattr(judge_mod, "judge_panel", stub_panel)

    result, _log = adj.adjudicate(
        {"A": A, "B": B}, paras, vocab,
        enable_llm_judge=True, max_judge_calls=3,
    )
    assert result["n_judge_calls"] == 3
    assert call_counter["n"] == 3


def test_precision_recall_formulas_hold():
    vocab = _mk_vocab()
    paras = [_mk_para("doc1", "p1"), _mk_para("doc1", "p2")]
    A = [
        _mk_ob("A", "doc1", "p1", "Provider", "draw up", "technical documentation"),
        _mk_ob("A", "doc1", "p2", "Provider", "monitor", "post-market log"),
    ]
    B = [
        _mk_ob("B", "doc1", "p1", "Provider", "draw up", "technical documentation"),
    ]
    result, _log = adj.adjudicate(
        {"A": A, "B": B}, paras, vocab, enable_llm_judge=False, max_judge_calls=0,
    )
    for name, m in result["per_extractor"].items():
        if m["tp"] + m["fp"]:
            assert abs(m["precision"] - m["tp"] / (m["tp"] + m["fp"])) < 1e-12
        if m["tp"] + m["fn"]:
            assert abs(m["recall"] - m["tp"] / (m["tp"] + m["fn"])) < 1e-12
