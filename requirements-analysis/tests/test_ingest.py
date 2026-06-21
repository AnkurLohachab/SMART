"""Ingest tests for synthetic HTML and the modal pre-filter."""
from __future__ import annotations

from pathlib import Path

import pytest

from lib import ingest as ing


def test_doc_id_from_path_strips_extension(tmp_path):
    p = tmp_path / "Some_File.PDF"
    p.write_bytes(b"x")
    assert ing.doc_id_from_path(p) == "some_file"


def test_file_sha256_is_stable(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    a = ing.file_sha256(p)
    b = ing.file_sha256(p)
    assert a == b
    assert len(a) == 64


def test_html_ingest_filters_by_modal(tmp_path):
    p = tmp_path / "doc.html"
    p.write_text(
        "<html><body>"
        "<p>Recommendation: providers should consider risk.</p>"
        "<p>The provider shall draw up documentation.</p>"
        "<p>This is unrelated content.</p>"
        "<script>shall must</script>"
        "</body></html>"
    )
    paragraphs = ing.ingest(p)
    assert len(paragraphs) == 1
    assert "shall draw up" in paragraphs[0].text


def test_unsupported_extension_raises(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello")
    with pytest.raises(ValueError, match="unsupported document type"):
        ing.ingest(p)


def test_html_ingest_strips_script_and_style(tmp_path):
    """Modal verbs in script/style/nav blocks must not produce paragraphs."""
    p = tmp_path / "doc.html"
    p.write_text(
        "<html><body>"
        "<nav>shall menu</nav>"
        "<style>.x { content: 'must'; }</style>"
        "<footer>shall footer</footer>"
        "<p>Real content with no modal.</p>"
        "</body></html>"
    )
    paragraphs = ing.ingest(p)
    assert paragraphs == []


def test_paragraph_immutable(tmp_path):
    p = tmp_path / "doc.html"
    p.write_text("<p>The provider shall draw up documentation.</p>")
    para = ing.ingest(p)[0]
    with pytest.raises(Exception):
        para.text = "tampered"
