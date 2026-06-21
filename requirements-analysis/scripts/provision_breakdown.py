"""Compute the canonical-provision breakdown from provisions.csv."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "sample_results" / "provisions.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "sample_results" / "provision_breakdown.json"
DEFAULT_OUTPUT_MD = Path(__file__).resolve().parent.parent / "sample_results" / "provision_breakdown.md"

UNKNOWN_PREFIX = "Unknown_"
SLOTS = ("bearer", "predicate", "artefact")
PLATFORM_COMPONENTS = ("Schema", "Lifecycle", "Schema+Lifecycle",
                       "Lifecycle+Chain", "Schema+Lifecycle+Chain", "Chain")


def n_unknown_slots(row: dict) -> int:
    return sum(1 for s in SLOTS if row[s].startswith(UNKNOWN_PREFIX))


def is_platform_attested(row: dict) -> bool:
    comp = row.get("smart_component", "")
    return comp in PLATFORM_COMPONENTS


@dataclass
class Breakdown:
    total_rows: int
    fully_canonicalised: int
    partial_one_slot_unknown: int
    partial_two_slots_unknown: int
    partial_three_slots_unknown: int
    fully_canonicalised_by_component: dict
    in_scope: int
    out_of_scope: int
    examples_fully_canonicalised: list
    examples_partial: list

    def to_dict(self) -> dict:
        return asdict(self)


def compute(rows: list[dict]) -> Breakdown:
    fully = [r for r in rows if n_unknown_slots(r) == 0]
    one_unk = [r for r in rows if n_unknown_slots(r) == 1]
    two_unk = [r for r in rows if n_unknown_slots(r) == 2]
    three_unk = [r for r in rows if n_unknown_slots(r) == 3]

    by_comp = Counter(r["smart_component"] or "(empty)" for r in fully)
    in_scope = sum(1 for r in fully if is_platform_attested(r))

    return Breakdown(
        total_rows=len(rows),
        fully_canonicalised=len(fully),
        partial_one_slot_unknown=len(one_unk),
        partial_two_slots_unknown=len(two_unk),
        partial_three_slots_unknown=len(three_unk),
        fully_canonicalised_by_component=dict(by_comp),
        in_scope=in_scope,
        out_of_scope=len(fully) - in_scope,
        examples_fully_canonicalised=[
            f"({r['bearer']}, {r['predicate']}, {r['artefact']}) "
            f"n_sources={r['n_sources']} component={r['smart_component']}"
            for r in fully[:3]
        ],
        examples_partial=[
            f"({r['bearer']}, {r['predicate']}, {r['artefact']}) "
            f"n_unknown={n_unknown_slots(r)} n_sources={r['n_sources']}"
            for r in (one_unk + two_unk)[:3]
        ],
    )


def print_summary(b: Breakdown) -> None:
    print("=" * 65)
    print("Provision breakdown")
    print("=" * 65)
    print(f"  total rows in provisions.csv     : {b.total_rows}")
    print(f"  fully canonicalised (real prov.) : {b.fully_canonicalised}")
    print(f"    - in SMART scope               : {b.in_scope}")
    print(f"    - recognised but out-of-scope  : {b.out_of_scope}")
    print(f"  partial (vocabulary-gap signals)")
    print(f"    - one slot Unknown_*           : {b.partial_one_slot_unknown}")
    print(f"    - two slots Unknown_*          : {b.partial_two_slots_unknown}")
    print(f"    - three slots Unknown_*        : {b.partial_three_slots_unknown}")
    print()
    print(f"  fully canonicalised by smart_component:")
    for k, v in sorted(b.fully_canonicalised_by_component.items(),
                        key=lambda kv: -kv[1]):
        print(f"    {k:<22} {v}")
    print()
    print("  sample fully-canonicalised rows:")
    for s in b.examples_fully_canonicalised:
        print(f"    {s}")
    print()
    print("  sample partial rows:")
    for s in b.examples_partial:
        print(f"    {s}")
    print("=" * 65)


def consistency_checks(rows: list[dict], b: Breakdown) -> None:
    assert b.total_rows == len(rows), \
        f"total_rows mismatch: {b.total_rows} vs {len(rows)}"

    sum_slots = (b.fully_canonicalised
                 + b.partial_one_slot_unknown
                 + b.partial_two_slots_unknown
                 + b.partial_three_slots_unknown)
    assert sum_slots == b.total_rows, \
        f"slot bins do not partition: sum={sum_slots} total={b.total_rows}"

    sum_comp = sum(b.fully_canonicalised_by_component.values())
    assert sum_comp == b.fully_canonicalised, \
        f"component breakdown sums to {sum_comp}, expected {b.fully_canonicalised}"

    assert b.in_scope + b.out_of_scope == b.fully_canonicalised, \
        "in_scope + out_of_scope must equal fully_canonicalised"

    in_scope_recount = sum(v for k, v in b.fully_canonicalised_by_component.items()
                            if k in PLATFORM_COMPONENTS)
    assert in_scope_recount == b.in_scope, \
        f"in_scope re-derivation mismatch: {in_scope_recount} vs {b.in_scope}"


def _fmt(r: dict) -> str:
    return f"({r['bearer']}, {r['predicate']}, {r['artefact']})"


def write_markdown(rows: list[dict], b: Breakdown, dst: Path) -> None:
    fully = [r for r in rows if n_unknown_slots(r) == 0]
    partial1 = [r for r in rows if n_unknown_slots(r) == 1]
    partial2 = [r for r in rows if n_unknown_slots(r) == 2]

    def by_freq(rs):
        return sorted(rs, key=lambda r: (-int(r["n_sources"]), r["bearer"],
                                          r["predicate"], r["artefact"]))

    in_scope = [r for r in fully if is_platform_attested(r)]
    out_of_scope = [r for r in fully if not is_platform_attested(r)]

    by_comp: dict[str, list[dict]] = {}
    for r in in_scope:
        by_comp.setdefault(r["smart_component"], []).append(r)

    out: list[str] = []
    out.append("# Provision breakdown\n")
    out.append("Auto-generated by `scripts/provision_breakdown.py` from "
               "`sample_results/provisions.csv`. Counts here mirror "
               "`provision_breakdown.json` and are anchored by the unit test "
               "`tests/test_provision_breakdown.py::test_breakdown_on_real_provisions_csv`.\n")

    out.append("## Summary\n")
    out.append("| Category | Count |")
    out.append("|---|---|")
    out.append(f"| Total canonical equivalence classes | {b.total_rows} |")
    out.append(f"| Fully canonicalised (real provisions) | {b.fully_canonicalised} |")
    out.append(f"| &nbsp;&nbsp;&nbsp; in SMART scope | {b.in_scope} |")
    out.append(f"| &nbsp;&nbsp;&nbsp; recognised but out-of-scope | {b.out_of_scope} |")
    out.append(f"| Partial (one slot Unknown_*) | {b.partial_one_slot_unknown} |")
    out.append(f"| Partial (two slots Unknown_*) | {b.partial_two_slots_unknown} |")
    out.append(f"| Partial (three slots Unknown_*) | {b.partial_three_slots_unknown} |\n")

    out.append("## In-scope provisions (93), grouped by SMART component\n")
    out.append("Each row: `(bearer, predicate, artefact) — n_sources × extractors`. "
               "Sorted by `n_sources` descending within each component "
               "(higher = more frequently restated across the corpus).\n")
    for comp in ["Schema", "Lifecycle", "Schema+Lifecycle",
                 "Lifecycle+Chain", "Schema+Lifecycle+Chain", "Chain"]:
        items = by_comp.get(comp, [])
        if not items:
            continue
        out.append(f"### {comp} ({len(items)} provisions)\n")
        for r in by_freq(items):
            out.append(f"- {_fmt(r)} — n_sources={r['n_sources']}, "
                       f"extractors=`{r['extractors']}`")
        out.append("")

    out.append(f"## Recognised but out-of-scope ({len(out_of_scope)})\n")
    out.append("These provisions canonicalise to artefacts that are explicitly "
               "marked `smart_section = N/A` in `vocabulary/coverage.csv` "
               "(out-of-scope for the platform's design — e.g. authority-side "
               "investigations, paid EU regulatory portals).\n")
    for r in by_freq(out_of_scope):
        out.append(f"- {_fmt(r)} — n_sources={r['n_sources']}")
    out.append("")

    out.append(f"## Partial — one slot Unknown_* ({len(partial1)})\n")
    out.append("Two of three slots resolved; one slot is a vocabulary-gap "
               "signal. Sorted by `n_sources` descending — the top entries "
               "are the highest-priority targets for vocabulary expansion.\n")
    for r in by_freq(partial1):
        out.append(f"- {_fmt(r)} — n_sources={r['n_sources']}")
    out.append("")

    out.append(f"## Partial — two slots Unknown_* ({len(partial2)})\n")
    out.append("Only one slot (typically the predicate) resolved. Less useful "
               "as evidence of a specific obligation; useful as a count of "
               "how often a given verb appears with unrecognised actor + "
               "object phrasing.\n")
    for r in by_freq(partial2):
        out.append(f"- {_fmt(r)} — n_sources={r['n_sources']}")
    out.append("")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = p.parse_args()

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 2

    with args.input.open() as f:
        rows = list(csv.DictReader(f))

    breakdown = compute(rows)
    consistency_checks(rows, breakdown)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(breakdown.to_dict(), indent=2))
    write_markdown(rows, breakdown, args.output_md)
    print_summary(breakdown)
    print(f"\nwrote {args.output}")
    print(f"wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
