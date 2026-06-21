"""Runner for D4' (adjudicate), D5 (variance decomposition), and D6 (FINAL_REPORT.md)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/work")

from lib import adjudicate as adj
from lib import ingest as ingest_mod
from lib import variance_decomp as vd
from lib import vocabulary as vocab_mod
from extractors.regex import RegexExtractor
from extractors.deepinfra import DeepInfraExtractor

OUT = Path("/work/outputs")
DOCS = Path("/work/docs")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def step_d5() -> Path:
    log("=== D5: variance decomposition ===")
    grid = OUT / "sensitivity_grid.csv"
    out = vd.write(grid, OUT / "variance_decomposition.json")
    data = json.loads(out.read_text())
    log(f"  cells: {data['n_cells']}")
    log(f"  grand_mean N: {data['grand_mean_N']:.1f}")
    log(f"  total variance: {data['total_variance']:.1f}")
    for f, c in data["components"].items():
        log(f"    {f:<14} fraction={c['fraction_of_total']:.3f} "
            f"between={c['between_variance']:.1f} levels={c['n_levels']}")
    log(f"  wrote {out}")
    return out


def step_d4_extractions() -> dict:
    """Run regex, Qwen, and Llama extractors; return extractions for adjudicate()."""
    log("=== D4': building extractions for {regex, Qwen, Llama} ===")
    manifest = ingest_mod.default_corpus_manifest(DOCS)
    paragraphs = []
    for entry in manifest:
        paragraphs.extend(ingest_mod.ingest(entry.path, source_access=entry.source_access))
    log(f"  paragraphs: {len(paragraphs)}")

    extractors = {
        "regex-baseline-v2[Mandatory+Recommended]": RegexExtractor(["Mandatory", "Recommended"]),
        "deepinfra[Qwen/Qwen2.5-72B-Instruct]":
            DeepInfraExtractor(model="Qwen/Qwen2.5-72B-Instruct"),
        "deepinfra[meta-llama/Llama-3.3-70B-Instruct-Turbo]":
            DeepInfraExtractor(model="meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    }

    extractions_by_extractor: dict[str, list] = {}
    for name, ex in extractors.items():
        rows = []
        for p in paragraphs:
            rows.extend(ex.extract(p))
        log(f"  {name}: {len(rows)} obligations")
        extractions_by_extractor[name] = rows

    return {"paragraphs": paragraphs, "extractions": extractions_by_extractor}


def step_d4_adjudicate(payload: dict, max_judge_calls: int = 200) -> tuple[dict, list]:
    log(f"=== D4': adjudicate (max_judge_calls={max_judge_calls}) ===")
    vocab = vocab_mod.load()
    result, judge_log = adj.adjudicate(
        payload["extractions"],
        payload["paragraphs"],
        vocab,
        enable_llm_judge=True,
        max_judge_calls=max_judge_calls,
    )
    adj.write(result, judge_log, OUT)
    log(f"  silver triples: {result['n_silver']}")
    log(f"  judge calls used: {result['n_judge_calls']}")
    for name, m in result["per_extractor"].items():
        prec = m["precision"]; rec = m["recall"]
        log(f"  {name:<60} P={prec:.3f}  R={rec:.3f}  TP={m['tp']}  FP={m['fp']}  FN={m['fn']}"
            if prec is not None and rec is not None
            else f"  {name:<60} P=N/A R=N/A TP={m['tp']} FP={m['fp']} FN={m['fn']}")
    return result, judge_log


def step_d6(d5_path: Path, adj_result: dict) -> Path:
    log("=== D6: FINAL_REPORT.md ===")
    d5 = json.loads(d5_path.read_text())

    lines = [
        "# Legal-evaluation — final report",
        "",
        "Track-D analysis of legal/regulatory provision extraction from an",
        "8-document, 420-paragraph corpus (EU AI Act, EU MDR, FDA AI/ML",
        "guidance × 3, TRIPOD+AI, ISO/IEC TR 29119-11 + 24028 landings).",
        "",
        "## D2 — extraction grid",
        "",
        "Three extractors, all on M / curated cell:",
        "",
        "| Extractor | n_raw | N (equiv. classes) | n_oov | n_covered |",
        "|---|---|---|---|---|",
    ]
    grid_csv = OUT / "sensitivity_grid.csv"
    for row in grid_csv.read_text().splitlines()[1:]:
        cols = row.split(",")
        if len(cols) < 7:
            continue
        if cols[0] != "M" or cols[2] != "curated":
            continue
        lines.append(f"| `{cols[1]}` | {cols[3]} | {cols[4]} | {cols[5]} | {cols[6]} |")
    lines += [
        "",
        "Excluded: `deepinfra[openai/gpt-oss-120b]` returned empty / truncated",
        "responses for 77 % of cells; the row is preserved in",
        "`sample_results/gpt_oss_120b_anomaly.md` with sample responses for audit.",
        "",
        "## D5 — variance decomposition over the sensitivity grid",
        "",
        f"- Cells in grid: **{d5['n_cells']}**",
        f"- Grand mean N: **{d5['grand_mean_N']:.1f}**",
        f"- Total variance σ²: **{d5['total_variance']:.1f}**",
        "",
        "| Factor | Levels | Between-group variance | Fraction of total |",
        "|---|---|---|---|",
    ]
    for f, c in d5["components"].items():
        lines.append(f"| `{f}` | {c['n_levels']} | {c['between_variance']:.1f} | {c['fraction_of_total']:.3f} |")
    lines += [
        f"| **residual** | — | {d5['residual_variance']:.1f} | "
        f"{d5['residual_variance'] / d5['total_variance']:.3f} |",
        "",
        "## D4' — silver standard + per-extractor precision/recall",
        "",
        f"- Silver-standard triples: **{adj_result['n_silver']}**",
        f"- LLM-judge calls used: **{adj_result['n_judge_calls']}**",
        "- Judge panel: Qwen/Qwen2.5-72B-Instruct, meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "",
        "| Extractor | TP | FP | FN | Precision | Recall |",
        "|---|---|---|---|---|---|",
    ]
    for name, m in adj_result["per_extractor"].items():
        p = f"{m['precision']:.3f}" if m["precision"] is not None else "—"
        r = f"{m['recall']:.3f}" if m["recall"] is not None else "—"
        lines.append(f"| `{name}` | {m['tp']} | {m['fp']} | {m['fn']} | {p} | {r} |")
    lines += [
        "",
        "## Provenance",
        "",
        f"- Corpus paragraphs: 420 (post-ingest); see `sample_results/partition.json`.",
        "- Extraction cache: `extractions/.cache/` (~7 k cells across 3 models).",
        "- Judge cache: `extractions/.judge_cache/`.",
        "- Audit trail: `sample_results/judge_log.json` lists every panel verdict.",
        "",
    ]
    out = OUT / "FINAL_REPORT.md"
    out.write_text("\n".join(lines))
    log(f"  wrote {out} ({len(lines)} lines)")
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    d5_path = step_d5()
    payload = step_d4_extractions()
    adj_result, _judge_log = step_d4_adjudicate(payload, max_judge_calls=200)
    step_d6(d5_path, adj_result)
    log("=== ALL DONE: D5, D4', D6 complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
