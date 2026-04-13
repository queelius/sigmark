"""Tests for sigmark.markdown module."""

from __future__ import annotations

import pytest

from sigmark.markdown import compute_body_hash, load_files, normalize_body, parse, render


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

    def test_existing_gpg_sig_field_preserved(self):
        text = "---\ntitle: Hello\ngpg_sig: old-sig\n---\nBody.\n"
        fm, body = parse(text)
        assert fm["gpg_sig"] == "old-sig"
        assert body == "Body.\n"

    def test_crlf_input_normalized(self):
        """Windows-authored files (CRLF) parse identically to LF."""
        lf = "---\ntitle: Hello\n---\nBody text.\n"
        crlf = lf.replace("\n", "\r\n")
        assert parse(crlf) == parse(lf)


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

    def test_roundtrip_preserves_formatting(self):
        """parse/render round-trip must not alter YAML formatting."""
        original = "---\ntitle: Hello World\ndate: 2026-01-01\ntags:\n  - test\n  - demo\n---\nBody text.\n"
        fm, body = parse(original)
        result = render(fm, body)
        assert result == original

    def test_empty_front_matter(self):
        result = render({}, "Body.\n")
        fm, body = parse(result)
        assert fm == {}
        assert body == "Body.\n"

    def test_render_with_gpg_sig(self):
        fm = {"title": "Hello", "gpg_sig": "ABC123"}
        result = render(fm, "Body.\n")
        assert "gpg_sig:" in result
        fm2, body2 = parse(result)
        assert fm2["gpg_sig"] == "ABC123"


class TestNormalizeBody:
    def test_strips_trailing_whitespace_per_line(self):
        result = normalize_body("line one  \nline two\t\n")
        assert result == "line one\nline two\n"

    def test_ensures_single_trailing_newline(self):
        result = normalize_body("line one\nline two\n\n\n")
        assert result == "line one\nline two\n"

    def test_empty_string(self):
        assert normalize_body("") == ""

    def test_whitespace_only(self):
        assert normalize_body("   \n  \n") == ""

    def test_idempotent(self):
        body = "Hello world.\n\nSecond paragraph.\n"
        first = normalize_body(body)
        second = normalize_body(first)
        assert first == second

    def test_no_trailing_newline_adds_one(self):
        result = normalize_body("no newline at end")
        assert result == "no newline at end\n"


class TestComputeBodyHash:
    def test_deterministic(self):
        body = "Hello world.\n"
        h1 = compute_body_hash(body)
        h2 = compute_body_hash(body)
        assert h1 == h2

    def test_sha256_prefix(self):
        result = compute_body_hash("Hello.\n")
        assert result.startswith("sha256:")
        # hex portion should be 64 chars
        assert len(result.split(":")[1]) == 64

    def test_changes_with_content(self):
        h1 = compute_body_hash("Content A.\n")
        h2 = compute_body_hash("Content B.\n")
        assert h1 != h2

    def test_ignores_trailing_whitespace_differences(self):
        h1 = compute_body_hash("line one  \nline two\n")
        h2 = compute_body_hash("line one\nline two\n")
        assert h1 == h2


class TestLoadFiles:
    def test_directory_finds_md_with_front_matter(self, tmp_content):
        files = load_files([tmp_content])
        filenames = {p.name for p in files}
        assert "index.md" in filenames
        # README.md has no front matter, should be excluded
        assert all("README" not in str(p) for p in files)

    def test_single_file(self, tmp_content):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        assert load_files([md_file]) == [md_file]

    def test_mixed_files_and_dirs(self, tmp_content):
        single = tmp_content / "post" / "hello-world" / "index.md"
        files = load_files([single, tmp_content / "post" / "second-post"])
        assert len(files) == 2

    def test_nonexistent_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_files([tmp_path / "nope.md"])

    def test_explicit_file_without_front_matter_included(self, tmp_content):
        """Explicit file args are returned as-is; callers validate front matter."""
        assert load_files([tmp_content / "README.md"]) == [tmp_content / "README.md"]

    def test_directory_skips_md_files_without_front_matter(self, tmp_content):
        """README.md is in tmp_content root but lacks front matter; directory walk skips it."""
        files = load_files([tmp_content])
        assert tmp_content / "README.md" not in files

    def test_directory_walk_accepts_crlf_header(self, tmp_path):
        """Windows-authored markdown (CRLF line endings) is recognized."""
        (tmp_path / "crlf.md").write_bytes(b"---\r\ntitle: CRLF\r\n---\r\nBody.\r\n")
        assert tmp_path / "crlf.md" in load_files([tmp_path])
