"""Check that every paper artefact category appears in the pipeline coverage output."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

PAPER_CATEGORIES = [
    ("Technical documentation",         "TechnicalDocumentation"),
    ("Training data governance",        "DataGovernancePolicy"),
    ("Transparency to deployers",       "TransparencyInformation"),
    ("Post-market monitoring",          "PostMarketMonitoringReport"),
    ("General safety & performance",    "PerformanceMetrics"),
    ("Clinical evaluation evidence",    "ExternallyValidatedMetrics"),
    ("Post-market surveillance",        "PostMarketSurveillancePlan"),
    ("Device nomenclature & UDI",       "DeviceIdentifier"),
    ("Predetermined change control",    "ChangeControlPlan"),
    ("Bias and subgroup analysis",      "SubgroupPerformance"),
    ("Performance reporting",           "PerformanceMetrics"),
    ("Source of data",                  "TrainingDataDescription"),
    ("Limitations",                     "LimitationsStatement"),
]


def audit(coverage_table_csv: Path) -> tuple[bool, list[dict]]:
    """Return (all_present, per_row_status) for paper categories vs coverage_table.csv."""
    have = set()
    if coverage_table_csv.exists():
        with coverage_table_csv.open() as fh:
            for row in csv.DictReader(fh):
                have.add(row["artefact"])
    rows = []
    for label, artefact in PAPER_CATEGORIES:
        rows.append({
            "paper_label": label,
            "expected_artefact": artefact,
            "found_in_output": artefact in have,
        })
    all_present = all(r["found_in_output"] for r in rows)
    return all_present, rows
