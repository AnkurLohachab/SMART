"""Variance decomposition tests."""
from lib.variance_decomp import decompose


def test_zero_variance_when_all_equal():
    grid = [
        {"tier": "M", "vocab_variant": "curated", "extractor": "x", "N": 100},
        {"tier": "M+R", "vocab_variant": "curated", "extractor": "x", "N": 100},
    ]
    out = decompose(grid)
    assert out["total_variance"] == 0
    assert out["components"] == {}


def test_decomposition_shape():
    grid = [
        {"tier": "M", "vocab_variant": "curated", "extractor": "regex", "N": 100},
        {"tier": "M", "vocab_variant": "curated", "extractor": "llm", "N": 200},
        {"tier": "M+R", "vocab_variant": "curated", "extractor": "regex", "N": 120},
        {"tier": "M+R", "vocab_variant": "curated", "extractor": "llm", "N": 240},
    ]
    out = decompose(grid)
    assert out["n_cells"] == 4
    assert "tier" in out["components"]
    assert "vocab_variant" in out["components"]
    assert "extractor" in out["components"]
    fracs = {k: v["fraction_of_total"] for k, v in out["components"].items()}
    assert fracs["extractor"] > fracs["tier"]
