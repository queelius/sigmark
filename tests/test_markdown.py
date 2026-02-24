"""Tests for sigmark.markdown module."""
from __future__ import annotations

import pytest

from sigmark.markdown import parse, render, resolve_paths


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


class TestRender:
    def test_basic_render(self):
        result = render({"title": "Hello", "date": "2026-01-01"}, "Body.\n")
        fm, body = parse(result)
        assert fm == {"title": "Hello", "date": "2026-01-01"}
        assert body == "Body.\n"

    def test_roundtrip(self):
        original = "---\ntitle: Hello\ntags:\n  - a\n  - b\n---\nBody text.\n"
        fm, body = parse(original)
        result = render(fm, body)
        fm2, body2 = parse(result)
        assert fm2 == fm
        assert body2 == body

    def test_empty_front_matter(self):
        result = render({}, "Body.\n")
        fm, body = parse(result)
        assert fm == {}
        assert body == "Body.\n"

    def test_render_with_signature(self):
        fm = {"title": "Hello", "signature": "ABC123"}
        result = render(fm, "Body.\n")
        assert "signature:" in result
        fm2, body2 = parse(result)
        assert fm2["signature"] == "ABC123"


class TestResolvePaths:
    def test_directory_finds_md_with_front_matter(self, tmp_content):
        paths = resolve_paths([tmp_content])
        filenames = {p.name for p in paths}
        assert "index.md" in filenames
        # README.md has no front matter, should be excluded
        assert all("README" not in str(p) for p in paths)

    def test_single_file(self, tmp_content):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        paths = resolve_paths([md_file])
        assert paths == [md_file]

    def test_mixed_files_and_dirs(self, tmp_content):
        single = tmp_content / "post" / "hello-world" / "index.md"
        paths = resolve_paths([single, tmp_content / "post" / "second-post"])
        assert len(paths) == 2

    def test_nonexistent_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_paths([tmp_path / "nope.md"])

    def test_file_without_front_matter_raises(self, tmp_content):
        with pytest.raises(ValueError, match="No YAML front matter"):
            resolve_paths([tmp_content / "README.md"])
