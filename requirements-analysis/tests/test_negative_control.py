"""Negative control specificity test."""
from __future__ import annotations

from lib import negative_control as nc


def test_negative_control_produces_few_or_no_covered_provisions():
    s = nc.run()
    assert s["n_covered"] <= 1, (
        f"cookbook excerpt mapped to {s['n_covered']} SMART artefacts — "
        f"the synonym table is over-permissive. Inspect sample_results/negative_control.json."
    )


def test_negative_control_paragraphs_are_ingested():
    """The control corpus has modal clauses, so ingest must surface paragraphs."""
    s = nc.run()
    assert s["n_paragraphs"] >= 3, \
        f"only {s['n_paragraphs']} paragraphs — ingest regression?"


def test_negative_control_specificity_observable():
    """The control corpus must map to 0 covered provisions."""
    s = nc.run()
    assert s["n_covered"] == 0, (
        f"NEGATIVE CONTROL FAILED — non-regulatory text mapped to "
        f"{s['n_covered']} SMART artefacts. The synonym table is too loose."
    )
