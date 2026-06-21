"""Unit tests for scripts/provision_breakdown.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent /
          "scripts" / "provision_breakdown.py")
spec = importlib.util.spec_from_file_location("provision_breakdown", SCRIPT)
pb = importlib.util.module_from_spec(spec)
sys.modules["provision_breakdown"] = pb
spec.loader.exec_module(pb)


def _row(b, p, a, comp="", n_sources="1", covered="True"):
    return {
        "bearer": b, "predicate": p, "artefact": a,
        "n_sources": n_sources, "covered": covered,
        "smart_section": "", "smart_component": comp,
        "extractors": "regex",
    }


def test_n_unknown_slots_counts_correctly():
    assert pb.n_unknown_slots(_row("Provider", "Disclose", "TechDoc")) == 0
    assert pb.n_unknown_slots(_row("Unknown_Bearer", "Disclose", "TechDoc")) == 1
    assert pb.n_unknown_slots(_row("Unknown_Bearer", "Disclose", "Unknown_Artefact")) == 2
    assert pb.n_unknown_slots(_row("Unknown_Bearer", "Unknown_Predicate",
                                    "Unknown_Artefact")) == 3


def test_is_platform_attested_only_for_listed_components():
    assert pb.is_platform_attested(_row("X", "Y", "Z", comp="Schema"))
    assert pb.is_platform_attested(_row("X", "Y", "Z", comp="Lifecycle"))
    assert pb.is_platform_attested(_row("X", "Y", "Z", comp="Schema+Lifecycle"))
    assert pb.is_platform_attested(_row("X", "Y", "Z", comp="Lifecycle+Chain"))
    assert not pb.is_platform_attested(_row("X", "Y", "Z", comp="N/A"))
    assert not pb.is_platform_attested(_row("X", "Y", "Z", comp=""))


def test_breakdown_partitions_input_exactly():
    rows = [
        _row("Provider", "Disclose", "TechDoc", comp="Schema"),
        _row("Manufacturer", "Maintain", "TechDoc", comp="Schema"),
        _row("Provider", "Notify", "ChangeNotification", comp="Lifecycle"),
        _row("Authority", "Assess", "CorrectiveAction", comp="Schema+Lifecycle"),
        _row("Authority", "Assess", "ElectronicSubmission", comp="N/A"),
        _row("Unknown_Bearer", "Verify", "TechDoc", comp="Schema"),
        _row("Unknown_Bearer", "Verify", "Unknown_Artefact", comp=""),
        _row("Provider", "Unknown_Predicate", "Unknown_Artefact", comp=""),
    ]
    b = pb.compute(rows)
    pb.consistency_checks(rows, b)

    assert b.total_rows == 8
    assert b.fully_canonicalised == 5
    assert b.partial_one_slot_unknown == 1
    assert b.partial_two_slots_unknown == 2
    assert b.partial_three_slots_unknown == 0
    assert b.in_scope == 4
    assert b.out_of_scope == 1


def test_breakdown_handles_empty_input():
    b = pb.compute([])
    pb.consistency_checks([], b)
    assert b.total_rows == 0
    assert b.fully_canonicalised == 0
    assert b.in_scope == 0


def test_consistency_check_catches_corruption():
    """If the breakdown is internally inconsistent, the assertion fires."""
    rows = [_row("Provider", "Disclose", "TechDoc", comp="Schema")]
    b = pb.compute(rows)
    b.fully_canonicalised = 999
    try:
        pb.consistency_checks(rows, b)
    except AssertionError:
        return
    raise AssertionError("consistency_checks should have raised")


def test_breakdown_on_real_provisions_csv():
    """compute() over the committed provisions.csv matches the reported numbers."""
    real_csv = SCRIPT.parent.parent / "sample_results" / "provisions.csv"
    if not real_csv.exists():
        return
    import csv
    rows = list(csv.DictReader(real_csv.open()))
    b = pb.compute(rows)
    pb.consistency_checks(rows, b)
    assert b.total_rows == 183
    assert b.fully_canonicalised == 98
    assert b.partial_one_slot_unknown == 75
    assert b.partial_two_slots_unknown == 10
    assert b.partial_three_slots_unknown == 0
    assert b.in_scope == 72
    assert b.out_of_scope == 26
