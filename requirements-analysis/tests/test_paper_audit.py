"""Paper-audit tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from lib import paper_audit as pa


def test_paper_categories_pinned():
    """All 13 paper categories are listed."""
    assert len(pa.PAPER_CATEGORIES) == 13


def test_paper_categories_reference_known_artefacts():
    """Every paper-side artefact label should exist in artefacts.csv."""
    from lib import vocabulary as vm
    v = vm.load()
    for _label, artefact in pa.PAPER_CATEGORIES:
        assert artefact in v.artefacts, (
            f"paper expects artefact {artefact!r} but it isn't in artefacts.csv"
        )


def test_audit_against_sample_coverage(tmp_path):
    """audit() returns True iff every expected artefact is in the file."""
    p = tmp_path / "coverage.csv"
    p.write_text(
        "artefact,smart_section,smart_component,sources,n_provisions,note\n"
        "TechnicalDocumentation,All 7 sections,Schema,,1,\n"
        "DataGovernancePolicy,Section 3,Schema,,1,\n"
    )
    ok, rows = pa.audit(p)
    assert ok is False
    found = [r["paper_label"] for r in rows if r["found_in_output"]]
    assert "Technical documentation" in found
    assert "Training data governance" in found
    assert "Limitations" not in found
