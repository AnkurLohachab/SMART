"""Diagnose pipeline outputs: pass/fail, issues, recommended fixes. Exit 0 on PASS, 1 on FAIL."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import median

OUT = Path(__file__).resolve().parent.parent / "sample_results"

N_MIN = 30
N_MAX = 400
NEG_CONTROL_MAX = 0
LLM_MIN_OBLIGATIONS = 10
MIN_DOCS_WITH_EXTRACTIONS = 4
LLM_NAME_PREFIXES = ("openrouter[", "llm[")


def _read_grid() -> list[dict]:
    p = OUT / "sensitivity_grid.csv"
    if not p.exists():
        return []
    return list(csv.DictReader(p.open()))


def _read_json(name: str) -> dict | None:
    p = OUT / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _negative_control_n_covered() -> int | None:
    p = OUT / "negative_control.txt"
    if not p.exists():
        return None
    for line in p.read_text().splitlines():
        line = line.strip()
        if line.startswith("n_covered:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except Exception:
                return None
    return None


def _per_doc_obligation_count() -> dict[str, int]:
    """Count rows per doc_id for the regex baseline at Mandatory tier."""
    extractions = OUT.parent / "extractions"
    if not extractions.exists():
        return {}
    candidates = sorted(extractions.glob("regex-baseline-v2*"))
    if not candidates:
        return {}
    target = candidates[0]
    result = {}
    for f in target.glob("*.json"):
        try:
            rows = json.loads(f.read_text())
            result[f.stem] = len(rows) if isinstance(rows, list) else 0
        except Exception:
            result[f.stem] = 0
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, default=0)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    issues: list[str] = []
    fixes: list[str] = []

    grid = _read_grid()
    if not grid:
        issues.append("sensitivity_grid.csv missing or empty")
        fixes.append("rerun")
        _write_and_exit(args.output, args.iter, issues, fixes)

    canonical = [r for r in grid
                 if r["tier"] == "M" and r["vocab_variant"] == "curated"
                 and r["extractor"].startswith("regex")]
    if not canonical:
        issues.append("no canonical regex row at (M, curated)")
        fixes.append("rerun")
    else:
        N = int(canonical[0]["N"])
        covered = int(canonical[0]["n_covered"])
        if covered < N_MIN:
            issues.append(f"canonical covered={covered} < {N_MIN}")
            fixes.append("expand_synonyms")
        if covered > N_MAX:
            issues.append(f"canonical covered={covered} > {N_MAX}")
            fixes.append("inspect_oov")

    nc = _negative_control_n_covered()
    if nc is None:
        issues.append("negative_control.txt missing or unparseable")
    elif nc > NEG_CONTROL_MAX:
        issues.append(f"negative control n_covered={nc} > {NEG_CONTROL_MAX}")
        fixes.append("tighten_synonyms")

    audit = _read_json("paper_audit_report.json")
    if audit is None:
        pass
    elif not audit.get("all_present"):
        missing = audit.get("missing", [])
        labels = [r.get("paper_label") for r in missing]
        pass

    per_doc = _per_doc_obligation_count()
    docs_with = sum(1 for v in per_doc.values() if v > 0)
    if docs_with < MIN_DOCS_WITH_EXTRACTIONS:
        issues.append(
            f"only {docs_with}/{len(per_doc)} docs produced obligations "
            f"(want ≥ {MIN_DOCS_WITH_EXTRACTIONS}); per-doc: {per_doc}"
        )
        fixes.append("expand_modal_tier")

    llm_rows = [r for r in grid
                if any(r["extractor"].startswith(pref) for pref in LLM_NAME_PREFIXES)]
    if not llm_rows:
        issues.append("no LLM extractors ran (rate-limited or no API key?)")
        fixes.append("rotate_llm_models")
    else:
        nonzero_llm = [r for r in llm_rows if int(r["n_raw"]) >= LLM_MIN_OBLIGATIONS]
        if not nonzero_llm:
            issues.append(
                f"all {len(llm_rows)} LLMs returned <{LLM_MIN_OBLIGATIONS} obligations "
                f"(probably rate-limited)"
            )
            fixes.append("rotate_llm_models")

    pass

    _write_and_exit(args.output, args.iter, issues, list(dict.fromkeys(fixes)))


def _write_and_exit(out_path: str, iter_n: int, issues: list[str], fixes: list[str]):
    payload = {
        "iter": iter_n,
        "pass": not issues,
        "issues": issues,
        "fixes": fixes,
        "thresholds": {
            "N_MIN": N_MIN, "N_MAX": N_MAX,
            "NEG_CONTROL_MAX": NEG_CONTROL_MAX,
            "LLM_MIN_OBLIGATIONS": LLM_MIN_OBLIGATIONS,
            "MIN_DOCS_WITH_EXTRACTIONS": MIN_DOCS_WITH_EXTRACTIONS,
        },
    }
    Path(out_path).write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    sys.exit(0 if payload["pass"] else 1)


if __name__ == "__main__":
    main()
