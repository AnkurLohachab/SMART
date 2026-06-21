"""Tests for scripts/coverage_evidence.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent /
          "scripts" / "coverage_evidence.py")
spec = importlib.util.spec_from_file_location("coverage_evidence", SCRIPT)
ce = importlib.util.module_from_spec(spec)
sys.modules["coverage_evidence"] = ce
spec.loader.exec_module(ce)


def test_format_quote_truncates_long_text():
    text = "a" * 1000
    out = ce._format_quote(text)
    assert out.startswith("> ")
    assert out.endswith("…")
    assert len(out) < 1000


def test_format_quote_normalises_whitespace():
    text = "line 1\n\nline 2\t\tend"
    assert ce._format_quote(text) == "> line 1 line 2 end"


def test_is_fully_canonicalised_rejects_unknown_slots():
    assert ce._is_fully_canonicalised(
        {"bearer": "Provider", "predicate": "draw_up", "artefact": "TechDoc"})
    assert not ce._is_fully_canonicalised(
        {"bearer": "Unknown_Bearer", "predicate": "draw_up", "artefact": "TechDoc"})
    assert not ce._is_fully_canonicalised(
        {"bearer": "Provider", "predicate": "draw_up", "artefact": "Unknown_Artefact"})


def test_evidence_doc_anchors_against_real_partition():
    """Generated doc has a section per known artefact and none for Unknown_*."""
    out_md = SCRIPT.parent.parent / "sample_results" / "coverage_evidence.md"
    if not out_md.exists():
        return
    text = out_md.read_text()
    for artefact in ("TechnicalDocumentation", "TransparencyInformation",
                     "ConformityAssessment", "DeviceIdentifier"):
        assert f"## `{artefact}`" in text, \
            f"expected artefact section for {artefact!r} in {out_md}"
    assert "## `Unknown_" not in text
