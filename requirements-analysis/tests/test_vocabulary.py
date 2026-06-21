"""Vocabulary integrity tests against the real CSVs under vocabulary/."""
from __future__ import annotations

from lib import vocabulary as vocab_mod


def test_load_vocabulary_succeeds():
    """The real vocabulary CSVs load without raising."""
    v = vocab_mod.load()
    assert v.bearers, "bearers.csv produced empty set"
    assert v.predicates, "predicates.csv produced empty set"
    assert v.artefacts, "artefacts.csv produced empty set"


def test_synonyms_reference_existing_canonicals():
    """Every synonym points to a canonical that exists in its set."""
    v = vocab_mod.load()
    for (slot, _phrase), canon in v.synonyms.items():
        if slot == "bearer":
            assert canon in v.bearers
        elif slot == "predicate":
            assert canon in v.predicates
        elif slot == "artefact":
            assert canon in v.artefacts
        else:
            raise AssertionError(f"unexpected slot {slot}")


def test_coverage_artefacts_all_known():
    """Every artefact in coverage.csv is in artefacts.csv."""
    v = vocab_mod.load()
    for row in v.coverage:
        assert row["artefact"] in v.artefacts


def test_canonical_lookup_lowercase_insensitive():
    v = vocab_mod.load()
    assert v.canonicalise("bearer", "Provider") == "Provider"
    assert v.canonicalise("bearer", "PROVIDER") == "Provider"
    assert v.canonicalise("bearer", "provider") == "Provider"


def test_canonical_lookup_unknown_returns_none():
    v = vocab_mod.load()
    assert v.canonicalise("bearer", "florist") is None
    assert v.canonicalise("predicate", "moonwalk") is None


def test_canonical_lookup_whitespace_insensitive():
    v = vocab_mod.load()
    assert v.canonicalise("bearer", "  provider  ") == "Provider"
    assert v.canonicalise("bearer", "providers   of\thigh-risk    ai\nsystems") == "Provider"
