"""Closed-vocabulary loader with integrity checks."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

VOCAB_DIR = Path(__file__).resolve().parent.parent / "vocabulary"


@dataclass(frozen=True)
class Vocabulary:
    bearers: frozenset[str]
    predicates: frozenset[str]
    artefacts: frozenset[str]
    synonyms: dict[tuple[str, str], str]
    coverage: tuple[dict, ...]
    modal_tiers: dict[str, str]

    def canonicalise(self, slot: str, phrase: str) -> str | None:
        """Map a raw phrase to its canonical entry, or None if OOV."""
        if not phrase:
            return None
        key = (slot, " ".join(phrase.lower().split()))
        return self.synonyms.get(key)

    def modals_for_tiers(self, tiers: Iterable[str]) -> tuple[str, ...]:
        wanted = set(tiers)
        return tuple(sorted(m for m, t in self.modal_tiers.items() if t in wanted))


def _load_canonicals(path: Path) -> frozenset[str]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    cans = [r["canonical"].strip() for r in rows if r["canonical"].strip()]
    if len(cans) != len(set(cans)):
        dups = {c for c in cans if cans.count(c) > 1}
        raise ValueError(f"duplicate canonicals in {path.name}: {dups}")
    return frozenset(cans)


def _load_synonyms(path: Path,
                   bearers: frozenset[str],
                   predicates: frozenset[str],
                   artefacts: frozenset[str]) -> dict[tuple[str, str], str]:
    syn: dict[tuple[str, str], str] = {}
    valid_canonicals = {
        "bearer": bearers,
        "predicate": predicates,
        "artefact": artefacts,
    }
    with path.open(encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.DictReader(fh), start=2):
            slot = row["slot"].strip().lower()
            phrase = " ".join(row["phrase"].lower().split())
            canon = row["canonical"].strip()
            if slot not in valid_canonicals:
                raise ValueError(f"{path.name} line {line_no}: unknown slot {slot!r}")
            if canon not in valid_canonicals[slot]:
                raise ValueError(
                    f"{path.name} line {line_no}: synonym {phrase!r} maps to "
                    f"unknown {slot} canonical {canon!r}"
                )
            key = (slot, phrase)
            if key in syn and syn[key] != canon:
                raise ValueError(
                    f"{path.name} line {line_no}: phrase {phrase!r} mapped to two "
                    f"canonicals: {syn[key]!r} and {canon!r}"
                )
            syn[key] = canon
    return syn


def _load_coverage(path: Path, artefacts: frozenset[str]) -> tuple[dict, ...]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.DictReader(fh), start=2):
            artefact = row["artefact"].strip()
            if artefact not in artefacts:
                raise ValueError(
                    f"{path.name} line {line_no}: unknown artefact {artefact!r}"
                )
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return tuple(rows)


VALID_TIERS = ("Mandatory", "Recommended", "Permitted")


def _load_modal_tiers(path: Path) -> dict[str, str]:
    """Load modal_tiers.csv into {phrase_lower: tier}."""
    if not path.exists():
        return {"shall": "Mandatory", "must": "Mandatory"}
    out: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.DictReader(fh), start=2):
            tier = row["tier"].strip()
            phrase = " ".join(row["modal"].lower().split())
            if tier not in VALID_TIERS:
                raise ValueError(f"{path.name} line {line_no}: bad tier {tier!r}")
            if phrase in out and out[phrase] != tier:
                raise ValueError(
                    f"{path.name} line {line_no}: phrase {phrase!r} mapped to two "
                    f"tiers: {out[phrase]!r} and {tier!r}"
                )
            out[phrase] = tier
    return out


def load(dir: Path = VOCAB_DIR) -> Vocabulary:
    bearers = _load_canonicals(dir / "bearers.csv")
    predicates = _load_canonicals(dir / "predicates.csv")
    artefacts = _load_canonicals(dir / "artefacts.csv")
    synonyms = _load_synonyms(dir / "synonyms.csv", bearers, predicates, artefacts)
    coverage = _load_coverage(dir / "coverage.csv", artefacts)
    modal_tiers = _load_modal_tiers(dir / "modal_tiers.csv")
    return Vocabulary(
        bearers=bearers,
        predicates=predicates,
        artefacts=artefacts,
        synonyms=synonyms,
        coverage=coverage,
        modal_tiers=modal_tiers,
    )
