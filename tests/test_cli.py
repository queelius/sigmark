"""Tests for sigmark CLI subcommands."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from sigmark import gpg, markdown
from sigmark.cli import main
from sigmark.markdown import parse


class TestSignCommand:
    def test_sign_adds_signature_to_front_matter(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(main, [
            "sign", "--key", "test@example.com",
            "--gpg-home", str(gpg_home),
            str(tmp_content / "post"),
        ])
        assert result.exit_code == 0
        text = (tmp_content / "post" / "hello-world" / "index.md").read_text()
        fm, body = parse(text)
        assert "signature" in fm
        assert "BEGIN PGP SIGNATURE" in fm["signature"]

    def test_sign_dry_run_does_not_modify(self, tmp_content, gpg_home):
        original = (tmp_content / "post" / "hello-world" / "index.md").read_text()
        runner = CliRunner()
        result = runner.invoke(main, [
            "--dry-run", "sign", "--key", "test@example.com",
            "--gpg-home", str(gpg_home),
            str(tmp_content / "post"),
        ])
        assert result.exit_code == 0
        assert (tmp_content / "post" / "hello-world" / "index.md").read_text() == original

    def test_sign_requires_key(self, tmp_content):
        runner = CliRunner()
        result = runner.invoke(main, ["sign", str(tmp_content)])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()


class TestVerifyCommand:
    def _sign_file(self, path: Path, gpg_home: Path) -> None:
        """Helper: sign a single file."""
        fm, body = parse(path.read_text())
        fm["signature"] = gpg.sign(body, key="test@example.com", gpg_home=gpg_home)
        path.write_text(markdown.render(fm, body))

    def test_verify_valid_signature(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        self._sign_file(md_file, gpg_home)
        runner = CliRunner()
        result = runner.invoke(main, [
            "verify", "--gpg-home", str(gpg_home), str(md_file),
        ])
        assert result.exit_code == 0

    def test_verify_tampered_file_fails(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        self._sign_file(md_file, gpg_home)
        # Tamper with body
        fm, _ = parse(md_file.read_text())
        md_file.write_text(markdown.render(fm, "Tampered body.\n"))
        runner = CliRunner()
        result = runner.invoke(main, [
            "verify", "--gpg-home", str(gpg_home), str(md_file),
        ])
        assert result.exit_code == 1

    def test_verify_unsigned_file_fails(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(main, [
            "verify", "--gpg-home", str(gpg_home),
            str(tmp_content / "post" / "hello-world" / "index.md"),
        ])
        assert result.exit_code == 1


class TestStripCommand:
    def test_strip_removes_signature(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["signature"] = "fake-sig"
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(main, ["strip", str(md_file)])
        assert result.exit_code == 0
        fm2, _ = parse(md_file.read_text())
        assert "signature" not in fm2

    def test_strip_dry_run(self, tmp_content):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["signature"] = "fake-sig"
        md_file.write_text(markdown.render(fm, body))
        original = md_file.read_text()
        runner = CliRunner()
        result = runner.invoke(main, ["--dry-run", "strip", str(md_file)])
        assert result.exit_code == 0
        assert md_file.read_text() == original

    def test_strip_unsigned_file_is_noop(self, tmp_content):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        original = md_file.read_text()
        runner = CliRunner()
        result = runner.invoke(main, ["strip", str(md_file)])
        assert result.exit_code == 0
        assert md_file.read_text() == original


class TestStatusCommand:
    def test_status_shows_unsigned(self, tmp_content):
        runner = CliRunner()
        result = runner.invoke(main, ["status", str(tmp_content / "post")])
        assert result.exit_code == 0
        assert "unsigned" in result.output.lower()

    def test_status_shows_valid(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["signature"] = gpg.sign(body, key="test@example.com", gpg_home=gpg_home)
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(main, [
            "status", "--gpg-home", str(gpg_home), str(md_file),
        ])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_status_shows_invalid(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["signature"] = "bogus-signature"
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(main, [
            "status", "--gpg-home", str(gpg_home), str(md_file),
        ])
        assert result.exit_code == 0
        assert "invalid" in result.output.lower()
