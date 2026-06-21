"""Main-effects variance decomposition of N across the sensitivity grid."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean

OUT = Path(__file__).resolve().parent.parent / "sample_results"


def decompose(grid_rows: list[dict]) -> dict:
    if not grid_rows:
        return {"error": "empty grid"}
    Ns = [int(r["N"]) for r in grid_rows]
    grand_mean = mean(Ns)
    total_var = sum((n - grand_mean) ** 2 for n in Ns) / len(Ns)
    if total_var == 0:
        return {"total_variance": 0, "components": {}, "n_cells": len(Ns)}

    components = {}
    for factor in ("tier", "vocab_variant", "extractor"):
        levels: dict[str, list[int]] = {}
        for r in grid_rows:
            levels.setdefault(r[factor], []).append(int(r["N"]))
        between = sum(
            len(vals) * (mean(vals) - grand_mean) ** 2
            for vals in levels.values()
        ) / len(Ns)
        components[factor] = {
            "between_variance": between,
            "fraction_of_total": between / total_var,
            "n_levels": len(levels),
            "level_means": {k: mean(v) for k, v in levels.items()},
        }
    explained = sum(c["between_variance"] for c in components.values())
    return {
        "n_cells": len(Ns),
        "grand_mean_N": grand_mean,
        "total_variance": total_var,
        "explained_variance": explained,
        "residual_variance": max(0.0, total_var - explained),
        "components": components,
    }


def write(grid_csv_path: Path, dst: Path = OUT / "variance_decomposition.json") -> Path:
    if not grid_csv_path.exists():
        raise FileNotFoundError(grid_csv_path)
    rows = list(csv.DictReader(grid_csv_path.open()))
    result = decompose(rows)
    dst.write_text(json.dumps(result, indent=2))
    return dst
