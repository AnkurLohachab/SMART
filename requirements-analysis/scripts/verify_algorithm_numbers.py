"""Re-derive every number in the pipeline algorithm from raw files; print PASS/FAIL per quantity."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from lib import ingest as ing
from extractors.deepinfra import DeepInfraExtractor
from extractors.regex import RegexExtractor

DOCS = HERE / "docs"
OUT = HERE / "sample_results"
CACHE = HERE / "extractions" / ".cache"
EXTRACTIONS = HERE / "extractions"

DEEPINFRA_PROMPT_VERSION = "v1-deepinfra"
DEFAULT_TEMPS = [(0.0, 1), (0.3, 2), (0.7, 2)]
PRODUCTION_LLMS = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
]

ALG_SPEC = {
    "|T|":     420,
    "|R|":     10921,
    "|Q|":     183,
    "|F|":     98,
    "|S|":     72,
    "|Q\\F|":  85,
    "|F\\S|":  26,
}


def cache_path(model: str, text: str, temperature: float, sample_idx: int) -> Path:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(b"\x00")
    h.update(DEEPINFRA_PROMPT_VERSION.encode())
    h.update(b"\x00")
    h.update(f"T={temperature}".encode())
    h.update(b"\x00")
    h.update(f"S={sample_idx}".encode())
    h.update(b"\x00")
    h.update(text.encode("utf-8", errors="replace"))
    return CACHE / f"{h.hexdigest()}.json"


def parse_obligations(content_str: str) -> list:
    if not content_str:
        return []
    s = re.sub(r"^```(?:json)?\s*", "", content_str.strip())
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        d = json.loads(s)
    except Exception:
        return []
    obs = d.get("obligations") if isinstance(d, dict) else d
    return obs if isinstance(obs, list) else []


def main() -> int:
    print("=" * 72)
    print("verify_algorithm_numbers — re-derive |T|, |R|, |Q|, |F|, |S| from raw data")
    print("=" * 72)

    print("\n[1] |T| — paragraph count via lib.ingest")
    manifest = ing.default_corpus_manifest(DOCS)
    all_paragraphs = []
    for entry in manifest:
        if not entry.path.exists():
            print(f"    ! missing: {entry.path}")
            continue
        paras = ing.ingest(entry.path, source_access=entry.source_access)
        print(f"    {entry.path.name:42s} paras={len(paras)}")
        all_paragraphs.extend(paras)
    T = len(all_paragraphs)
    print(f"    --- |T| = {T}")

    print("\n[2] |R_regex| — regex-baseline-v2[Mandatory+Recommended]")
    rdir = EXTRACTIONS / "regex-baseline-v2[Mandatory+Recommended]"
    regex_total = 0
    for fn in sorted(os.listdir(rdir)):
        if not fn.endswith(".json"):
            continue
        with open(rdir / fn) as fh:
            rows = json.load(fh)
        n = len(rows) if isinstance(rows, list) else 0
        print(f"    {fn:42s} n={n}")
        regex_total += n
    print(f"    --- |R_regex| = {regex_total}")

    llm_totals: dict[str, int] = {}
    for model in PRODUCTION_LLMS:
        print(f"\n[3] |R_{model.split('/')[-1]}| — production extract() over cached paragraphs")
        ex = DeepInfraExtractor(model=model, api_key="cache-only")
        rows: list = []
        for p in all_paragraphs:
            rows.extend(ex.extract(p))
        print(f"    rows emitted by extract() (post-filter): {len(rows)}")
        llm_totals[model] = len(rows)

    print("\n[4] |R| — sum across all extractors")
    R_total = regex_total + sum(llm_totals.values())
    print(f"    regex                                   : {regex_total}")
    for m, n in llm_totals.items():
        print(f"    {m.split('/')[-1]:40s}: {n}")
    print(f"    --- |R| = {R_total}")

    print("\n[5] |Q|, |F|, |S| — from partition.json / provision_breakdown.json")
    with open(OUT / "partition.json") as f:
        partition = json.load(f)
    Q = len(partition)
    with open(OUT / "provision_breakdown.json") as f:
        pb = json.load(f)
    F = pb["fully_canonicalised"]
    S = pb["in_scope"]
    F_minus_S = pb["out_of_scope"]
    Q_minus_F = Q - F
    print(f"    |Q|        = {Q}")
    print(f"    |F|        = {F}")
    print(f"    |S|        = {S}")
    print(f"    |F \\ S|    = {F_minus_S}")
    print(f"    |Q \\ F|    = {Q_minus_F}")

    print("\n" + "=" * 72)
    print("RECONCILIATION  spec  vs  actual")
    print("=" * 72)
    actual = {
        "|T|":    T,
        "|R|":    R_total,
        "|Q|":    Q,
        "|F|":    F,
        "|S|":    S,
        "|Q\\F|": Q_minus_F,
        "|F\\S|": F_minus_S,
    }
    failures = 0
    for k, spec_v in ALG_SPEC.items():
        a = actual[k]
        ok = (spec_v == a)
        mark = "PASS" if ok else "FAIL"
        print(f"  {k:8s}  spec={spec_v:>6}   actual={a:>6}   {mark}")
        if not ok:
            failures += 1
    print("\nRegex per-extractor breakdown (for the |R| funnel):")
    print(f"  regex                                   : {regex_total}")
    for m, n in llm_totals.items():
        print(f"  {m.split('/')[-1]:40s}: {n}")
    print(f"  --- |R| = {R_total}")
    print("\nResult:", "ALL PASS" if failures == 0 else f"{failures} MISMATCH(ES)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
