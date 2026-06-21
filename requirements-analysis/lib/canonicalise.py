"""Map ExtractedObligations onto canonical (bearer, predicate, artefact) triples and merge equivalence classes."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from lib.types import CanonicalProvision, ExtractedObligation
from lib.vocabulary import Vocabulary

UNKNOWN = {
    "bearer": "Unknown_Bearer",
    "predicate": "Unknown_Predicate",
    "artefact": "Unknown_Artefact",
}


def _longest_match(phrase: str, slot: str, vocab: Vocabulary) -> str | None:
    """Return the longest synonym appearing as a substring of phrase, or None."""
    phrase_lc = " ".join(phrase.lower().split())
    direct = vocab.canonicalise(slot, phrase_lc)
    if direct:
        return direct
    candidates = []
    for (s, p), canon in vocab.synonyms.items():
        if s != slot:
            continue
        if p in phrase_lc:
            candidates.append((len(p), p, canon))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def canonicalise_one(o: ExtractedObligation, vocab: Vocabulary) \
        -> tuple[str, str, str, list[str]]:
    oov: list[str] = []

    bearer = _longest_match(o.bearer_phrase, "bearer", vocab)
    if not bearer:
        bearer = UNKNOWN["bearer"]
        oov.append(f"bearer:{o.bearer_phrase!r}")

    predicate = _longest_match(o.predicate_phrase, "predicate", vocab)
    if not predicate:
        predicate = UNKNOWN["predicate"]
        oov.append(f"predicate:{o.predicate_phrase!r}")

    artefact = _longest_match(o.artefact_phrase, "artefact", vocab)
    if not artefact:
        artefact = UNKNOWN["artefact"]
        oov.append(f"artefact:{o.artefact_phrase!r}")

    return bearer, predicate, artefact, oov


def canonicalise(obligations: Iterable[ExtractedObligation],
                 vocab: Vocabulary) -> list[CanonicalProvision]:
    bucket: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"sources": [], "verbatims": [], "extractors": [], "oov": []}
    )
    for o in obligations:
        b, p, a, oov = canonicalise_one(o, vocab)
        key = (b, p, a)
        bucket[key]["sources"].append((o.doc_id, o.locator))
        bucket[key]["verbatims"].append(o.verbatim)
        bucket[key]["extractors"].append(o.extractor)
        if oov:
            bucket[key]["oov"].extend(oov)
    out: list[CanonicalProvision] = []
    for (b, p, a), agg in sorted(bucket.items()):
        seen: set[tuple] = set()
        paired: list[tuple[tuple[str, str], str]] = []
        for src, ver in zip(agg["sources"], agg["verbatims"]):
            key2 = (src, ver)
            if key2 in seen:
                continue
            seen.add(key2)
            paired.append((src, ver))
        paired.sort(key=lambda sv: (sv[0][0], sv[0][1], sv[1]))
        sources_aligned = tuple(p[0] for p in paired)
        verbatims_aligned = tuple(p[1] for p in paired)
        out.append(CanonicalProvision(
            bearer=b,
            predicate=p,
            artefact=a,
            sources=sources_aligned,
            verbatims=verbatims_aligned,
            extractors=tuple(sorted(set(agg["extractors"]))),
            oov_terms=tuple(sorted(set(agg["oov"]))),
        ))
    return out
