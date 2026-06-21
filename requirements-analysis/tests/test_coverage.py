"""Coverage join and grouped-table tests."""
from __future__ import annotations

from lib import canonicalise as cm
from lib import coverage as cov
from lib import vocabulary as vm
from lib.types import ExtractedObligation


def _ob(b, p, a):
    return ExtractedObligation(
        extractor="t", doc_id="d", locator="¶1",
        verbatim="v", modal="shall",
        bearer_phrase=b, predicate_phrase=p, artefact_phrase=a,
    )


def test_per_provision_coverage_marks_known_artefacts():
    v = vm.load()
    rows = cm.canonicalise([_ob("provider", "draw up", "technical documentation")], v)
    out = cov.coverage_per_provision(rows, v)
    assert len(out) == 1
    assert out[0]["covered"] is True
    assert out[0]["smart_component"]


def test_per_provision_coverage_marks_oov_uncovered():
    v = vm.load()
    rows = cm.canonicalise([_ob("provider", "draw up", "moon dust")], v)
    out = cov.coverage_per_provision(rows, v)
    assert len(out) == 1
    assert out[0]["covered"] is False


def test_grouped_aggregates_by_artefact():
    v = vm.load()
    rows = cm.canonicalise([
        _ob("provider", "draw up", "technical documentation"),
        _ob("manufacturer", "prepare", "technical documentation"),
    ], v)
    grouped = cov.grouped_for_paper(rows, v)
    techdoc_rows = [r for r in grouped if r["artefact"] == "TechnicalDocumentation"]
    assert len(techdoc_rows) == 1
    assert techdoc_rows[0]["n_provisions"] == 2
