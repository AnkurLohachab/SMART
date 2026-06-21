"""Apply targeted, idempotent auto-fixes from a diagnosis JSON; each appends to vocabulary/_audit.log."""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOCAB = ROOT / "vocabulary"
OUT = ROOT / "sample_results"
ENV = ROOT / ".env"
AUDIT_LOG = VOCAB / "_audit.log"


def _audit(msg: str) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")



def _existing_synonyms() -> set[tuple[str, str]]:
    syn = VOCAB / "synonyms.csv"
    rows = list(csv.DictReader(syn.open()))
    return {(r["slot"].lower(), r["phrase"].lower()) for r in rows}


def _existing_canonicals(slot: str) -> set[str]:
    src = {"bearer": "bearers.csv", "predicate": "predicates.csv",
           "artefact": "artefacts.csv"}[slot]
    rows = list(csv.DictReader((VOCAB / src).open()))
    return {r["canonical"].strip() for r in rows if r["canonical"].strip()}


def _shortest_substring_canonical(slot: str, phrase: str) -> str | None:
    candidates = _existing_canonicals(slot)
    phrase_lc = phrase.lower()
    for c in candidates:
        words = re.findall(r"[A-Z][a-z]+|\d+", c)
        guess = " ".join(words).lower()
        if guess and guess in phrase_lc:
            return c
    return None


def expand_synonyms(top_n: int = 25) -> int:
    partition = OUT / "partition.json"
    if not partition.exists():
        _audit("expand_synonyms: partition.json missing — no-op")
        return 0
    data = json.loads(partition.read_text())
    counter = Counter()
    for r in data:
        for term in r.get("oov_terms", []):
            slot, _, phrase = term.partition(":")
            phrase = phrase.strip().strip("'\"")
            if not phrase or len(phrase) > 200:
                continue
            counter[(slot, phrase[:120].lower())] += 1
    existing = _existing_synonyms()
    added = 0
    new_rows: list[tuple[str, str, str]] = []
    for (slot, phrase), _count in counter.most_common(top_n):
        if (slot, phrase) in existing:
            continue
        suggested = _shortest_substring_canonical(slot, phrase)
        if not suggested:
            continue
        new_rows.append((slot, phrase, suggested))
        added += 1
    if not new_rows:
        _audit("expand_synonyms: no new mappable OOVs")
        return 0
    with (VOCAB / "synonyms.csv").open("a", newline="") as fh:
        w = csv.writer(fh)
        for r in new_rows:
            w.writerow(r)
    _audit(f"expand_synonyms: appended {added} rows: " +
           ", ".join(f"{s}:{p[:30]}->{c}" for s, p, c in new_rows[:5]))
    return added



COOKBOOK_BLACKLIST = {
    "bearer": ["chef", "baker", "cook", "cooks", "bakers", "the chef",
               "the baker"],
    "predicate": ["whisk", "crack", "fold", "wipe", "sharpen", "heat"],
    "artefact": ["egg", "eggs", "pan", "blade", "knife", "dough", "yeast",
                 "omelette", "spatula"],
}


def tighten_synonyms() -> int:
    syn_path = VOCAB / "synonyms.csv"
    rows = list(csv.DictReader(syn_path.open()))
    keep = []
    removed = 0
    for r in rows:
        slot = r["slot"].lower()
        phrase = r["phrase"].lower().strip()
        if phrase in COOKBOOK_BLACKLIST.get(slot, []):
            removed += 1
            continue
        keep.append(r)
    if not removed:
        _audit("tighten_synonyms: no cookbook-blacklist hits")
        return 0
    with syn_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        for r in keep:
            w.writerow(r)
    _audit(f"tighten_synonyms: removed {removed} cookbook-overlapping rows")
    return removed



MODEL_POOL = [
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-20b:free",
    "qwen/qwen3-coder:free",
    "google/gemma-4-31b-it:free",
]


def rotate_llm_models() -> int:
    if not ENV.exists():
        _audit("rotate_llm_models: .env missing")
        return 0
    text = ENV.read_text()
    m = re.search(r"^OPENROUTER_MODELS=(.*)$", text, re.MULTILINE)
    current = m.group(1).strip().split(",") if m else []
    current = [x.strip() for x in current if x.strip()]
    fresh_candidates = [x for x in MODEL_POOL if x not in current]
    if not fresh_candidates:
        _audit("rotate_llm_models: pool exhausted")
        return 0
    new_list = (current[1:] if len(current) > 1 else []) + [fresh_candidates[0]]
    new_line = "OPENROUTER_MODELS=" + ",".join(new_list)
    if m:
        text = re.sub(r"^OPENROUTER_MODELS=.*$", new_line, text, count=1, flags=re.MULTILINE)
    else:
        text += "\n" + new_line + "\n"
    ENV.write_text(text)
    _audit(f"rotate_llm_models: {current} to {new_list}")
    return 1



def expand_modal_tier() -> int:
    """Flip RegexExtractor() default in run.py from Mandatory to M+R."""
    run_py = ROOT / "run.py"
    text = run_py.read_text()
    old = '"regex": RegexExtractor,'
    new = '"regex": lambda: __import__("extractors.regex", fromlist=["RegexExtractor"]).RegexExtractor(tiers=("Mandatory", "Recommended")),'
    if old in text:
        text = text.replace(old, new, 1)
        run_py.write_text(text)
        _audit("expand_modal_tier: run.py default extractor to M+R")
        return 1
    _audit("expand_modal_tier: no-op (already patched or not found)")
    return 0



FIX_TABLE = {
    "expand_synonyms": expand_synonyms,
    "tighten_synonyms": tighten_synonyms,
    "rotate_llm_models": rotate_llm_models,
    "expand_modal_tier": expand_modal_tier,
    "inspect_oov": lambda: 0,
    "inspect_paper_audit": lambda: 0,
    "rerun": lambda: 0,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnosis", required=True)
    args = ap.parse_args()
    diag = json.loads(Path(args.diagnosis).read_text())
    applied = 0
    for fix in diag.get("fixes", []):
        fn = FIX_TABLE.get(fix)
        if not fn:
            _audit(f"unknown fix: {fix} (skipped)")
            continue
        n = fn()
        applied += int(bool(n))
        print(f"  fix {fix} applied={bool(n)}")
    return 0 if applied else 1


if __name__ == "__main__":
    raise SystemExit(main())
