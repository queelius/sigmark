"""Tests for sigmark.markdown module."""
from __future__ import annotations

import pytest

from sigmark.markdown import parse


class TestParse:
    def test_basic_front_matter_and_body(self):
        text = "---\ntitle: Hello\ndate: 2026-01-01\n---\nBody text.\n"
        fm, body = parse(text)
        assert fm == {"title": "Hello", "date": "2026-01-01"}
        assert body == "Body text.\n"

    def test_multiline_body(self):
        text = "---\ntitle: Post\n---\nParagraph one.\n\nParagraph two.\n"
        fm, body = parse(text)
        assert body == "Paragraph one.\n\nParagraph two.\n"

    def test_no_front_matter_raises(self):
        with pytest.raises(ValueError, match="No YAML front matter"):
            parse("# Just a heading\n\nNo front matter here.\n")

    def test_empty_front_matter(self):
        text = "---\n---\nBody only.\n"
        fm, body = parse(text)
        assert fm == {}
        assert body == "Body only.\n"

    def test_front_matter_with_list_values(self):
        text = "---\ntitle: Hello\ntags:\n  - a\n  - b\n---\nBody.\n"
        fm, body = parse(text)
        assert fm["tags"] == ["a", "b"]

    def test_existing_signature_field_preserved(self):
        text = "---\ntitle: Hello\nsignature: old-sig\n---\nBody.\n"
        fm, body = parse(text)
        assert fm["signature"] == "old-sig"
        assert body == "Body.\n"
