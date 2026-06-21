"""Re-run the LLM extract() path and count parsed vs survived vs dropped rows."""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from lib import ingest as ing
from extractors.deepinfra import DeepInfraExtractor, _parse_json_obligations
from extractors.base import validate_obligation, ExtractedObligation

DOCS = HERE / "docs"
PRODUCTION_LLMS = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
]

def main() -> int:
    manifest = ing.default_corpus_manifest(DOCS)
    paragraphs = []
    for entry in manifest:
        if entry.path.exists():
            paragraphs.extend(ing.ingest(entry.path, source_access=entry.source_access))
    print(f"paragraphs: {len(paragraphs)}")

    grand_parsed = grand_survived = grand_dropped_modal = grand_dropped_validate = 0
    for model in PRODUCTION_LLMS:
        ex = DeepInfraExtractor(model=model, api_key="cache-only")
        parsed = survived = dropped_modal = dropped_validate = 0
        for p in paragraphs:
            for temperature, n_samples in ex.cfg.temps:
                for sample_idx in range(n_samples):
                    content = ex._one_call(p, temperature, sample_idx)
                    rows = _parse_json_obligations(content)
                    parsed += len(rows)
                    for r in rows:
                        modal = " ".join(str(r.get("modal", "")).lower().split())
                        if modal not in ex._known_modals:
                            dropped_modal += 1
                            continue
                        try:
                            ob = ExtractedObligation(
                                extractor=f"{ex.name}@T{temperature}#{sample_idx}",
                                doc_id=p.doc_id, locator=p.locator,
                                verbatim=str(r.get("verbatim", "")).strip(),
                                modal=modal,
                                bearer_phrase=str(r.get("bearer_phrase", "")).strip()[:300],
                                predicate_phrase=str(r.get("predicate_phrase", "")).strip()[:80],
                                artefact_phrase=str(r.get("artefact_phrase", "")).strip()[:300],
                            )
                            validate_obligation(ob, p)
                            survived += 1
                        except (ValueError, TypeError):
                            dropped_validate += 1
        dropped = parsed - survived
        print(f"\n{model}")
        print(f"  parsed (pre-filter)      : {parsed}")
        print(f"  survived -> |R| share    : {survived}")
        print(f"  dropped (modal)          : {dropped_modal}")
        print(f"  dropped (validate)       : {dropped_validate}")
        print(f"  dropped (total)          : {dropped}")
        grand_parsed += parsed; grand_survived += survived
        grand_dropped_modal += dropped_modal; grand_dropped_validate += dropped_validate

    grand_dropped = grand_parsed - grand_survived
    print("\n" + "=" * 60)
    print(f"LLM parsed (pre-filter total) : {grand_parsed}")
    print(f"LLM survived (= |R| LLM share): {grand_survived}")
    print(f"LLM dropped (modal)           : {grand_dropped_modal}")
    print(f"LLM dropped (validate)        : {grand_dropped_validate}")
    print(f"LLM dropped (total)           : {grand_dropped}")
    print(f"\nPaper claims: 3759 dropped, LLM retained = 3685+6693 = {3685+6693}")
    print(f"Implied raw total = 543 + {grand_parsed} = {543 + grand_parsed}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
