"""Subsumption ontology tests."""
from __future__ import annotations

import pytest

from lib import subsumption as sub
from lib.types import CanonicalProvision


def _cp(b, p, a):
    return CanonicalProvision(
        bearer=b, predicate=p, artefact=a,
        sources=(("d", "¶"),), verbatims=("v",), extractors=("e",),
    )


def test_table_loads_without_cycles():
    """No subsumption cycle in vocabulary/subsumption.csv."""
    sub._load_table.cache_clear()
    sub._load_table()


def test_self_subsumes():
    assert sub.is_subsumed_by("bearer", "Provider", "Provider") is True
    assert sub.is_subsumed_by("artefact", "TechnicalDocumentation",
                              "TechnicalDocumentation") is True


def test_direct_subsumption():
    assert sub.is_subsumed_by("bearer", "Manufacturer", "Provider") is True
    assert sub.is_subsumed_by("artefact", "RiskManagementSystem",
                              "TechnicalDocumentation") is True


def test_transitive_subsumption():
    """SubgroupPerformance ⊑ PerformanceMetrics ⊑ TechnicalDocumentation."""
    assert sub.is_subsumed_by("artefact", "SubgroupPerformance",
                              "TechnicalDocumentation") is True


def test_unrelated_returns_false():
    assert sub.is_subsumed_by("bearer", "Provider", "Manufacturer") is False
    assert sub.is_subsumed_by("artefact", "DeviceIdentifier",
                              "PerformanceMetrics") is False


def test_formal_equivalence():
    a = _cp("Provider", "Produce", "TechnicalDocumentation")
    b = _cp("Provider", "Produce", "TechnicalDocumentation")
    c = _cp("Manufacturer", "Produce", "TechnicalDocumentation")
    assert sub.formally_equivalent(a, b) is True
    assert sub.formally_equivalent(a, c) is False


def test_formal_subsumption():
    """A more specific provision is subsumed by a more general one."""
    specific = _cp("Manufacturer", "Verify", "RiskManagementSystem")
    general = _cp("Provider",     "Assess", "TechnicalDocumentation")
    assert sub.formally_subsumed(specific, general) is True
    assert sub.formally_subsumed(general, specific) is False
