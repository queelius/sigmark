"""Tests for sigmark CLI subcommands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from sigmark import gpg, markdown
from sigmark.cli import main
from sigmark.markdown import parse


class TestSignCommand:
    def test_sign_adds_signature_to_front_matter(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post"),
            ],
        )
        assert result.exit_code == 0
        text = (tmp_content / "post" / "hello-world" / "index.md").read_text()
        fm, body = parse(text)
        assert "gpg_sig" in fm
        assert "BEGIN PGP SIGNATURE" in fm["gpg_sig"]

    def test_sign_dry_run_does_not_modify(self, tmp_content, gpg_home):
        original = (tmp_content / "post" / "hello-world" / "index.md").read_text()
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--dry-run",
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post"),
            ],
        )
        assert result.exit_code == 0
        assert (tmp_content / "post" / "hello-world" / "index.md").read_text() == original

    def test_sign_populates_metadata_fields(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post" / "hello-world" / "index.md"),
            ],
        )
        assert result.exit_code == 0
        text = (tmp_content / "post" / "hello-world" / "index.md").read_text()
        fm, body = parse(text)
        assert "gpg_sig_date" in fm
        assert fm["gpg_sig_date"].endswith("Z")
        assert "gpg_body_hash" in fm
        assert fm["gpg_body_hash"].startswith("sha256:")


class TestVerifyCommand:
    def _sign_file(self, path: Path, gpg_home: Path) -> None:
        """Helper: sign a single file using normalized body."""
        fm, body = parse(path.read_text())
        normalized = markdown.normalize_body(body)
        fm["gpg_sig"] = gpg.sign(normalized, key="test@example.com", gpg_home=gpg_home)
        fm["gpg_body_hash"] = markdown.compute_body_hash(body)
        path.write_text(markdown.render(fm, body))

    def test_verify_valid_signature(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        self._sign_file(md_file, gpg_home)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "verify",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        assert result.exit_code == 0

    def test_verify_tampered_file_fails(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        self._sign_file(md_file, gpg_home)
        # Tamper with body
        fm, _ = parse(md_file.read_text())
        md_file.write_text(markdown.render(fm, "Tampered body.\n"))
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "verify",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        assert result.exit_code == 1

    def test_verify_unsigned_file_fails(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "verify",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post" / "hello-world" / "index.md"),
            ],
        )
        assert result.exit_code == 1


class TestStripCommand:
    def test_strip_removes_signature(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["gpg_sig"] = "fake-sig"
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(main, ["strip", str(md_file)])
        assert result.exit_code == 0
        fm2, _ = parse(md_file.read_text())
        assert "gpg_sig" not in fm2

    def test_strip_dry_run(self, tmp_content):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["gpg_sig"] = "fake-sig"
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
        normalized = markdown.normalize_body(body)
        fm["gpg_sig"] = gpg.sign(normalized, key="test@example.com", gpg_home=gpg_home)
        fm["gpg_body_hash"] = markdown.compute_body_hash(body)
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "status",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_status_shows_invalid(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["gpg_sig"] = "bogus-signature"
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "status",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        assert result.exit_code == 0
        assert "invalid" in result.output.lower()

    def test_status_json_output(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "status",
                "--json",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post"),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total" in data
        assert "signed" in data
        assert "unsigned" in data
        assert "stale" in data
        assert "files" in data
        assert data["total"] == 2
        assert data["unsigned"] == 2

    def test_status_json_shows_signed(self, tmp_content, gpg_home):
        # Sign one file via CLI
        runner = CliRunner()
        runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post" / "hello-world" / "index.md"),
            ],
        )
        result = runner.invoke(
            main,
            [
                "status",
                "--json",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post"),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["signed"] == 1
        assert data["unsigned"] == 1

    def test_status_json_stale(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        # Sign via CLI
        runner = CliRunner()
        runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        # Modify body but keep front matter (making hash stale)
        fm, _ = parse(md_file.read_text())
        md_file.write_text(markdown.render(fm, "Modified body content.\n"))
        result = runner.invoke(
            main,
            [
                "status",
                "--json",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["stale"] == 1


class TestSignSkipAndForce:
    def test_skip_already_signed_with_current_hash(self, tmp_content, gpg_home):
        runner = CliRunner()
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        # First sign
        runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        # Second sign without --force: should skip
        result = runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        assert result.exit_code == 0
        assert "skipped 1" in result.output.lower()

    def test_force_re_signs(self, tmp_content, gpg_home):
        runner = CliRunner()
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        # First sign
        runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(md_file),
            ],
        )
        # Second sign with --force: should sign
        result = runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                "--force",
                str(md_file),
            ],
        )
        assert result.exit_code == 0
        assert "signed 1" in result.output.lower()
        assert "skipped 0" in result.output.lower()

    def test_summary_counts(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "sign",
                "--key",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post"),
            ],
        )
        assert result.exit_code == 0
        # Both files signed
        assert "signed 2" in result.output.lower()
        assert "skipped 0" in result.output.lower()
        assert "errors 0" in result.output.lower()


class TestDefaultKeyBehavior:
    def test_sign_without_key_uses_default(self, tmp_content, gpg_home):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "sign",
                "--gpg-home",
                str(gpg_home),
                str(tmp_content / "post" / "hello-world" / "index.md"),
            ],
        )
        assert result.exit_code == 0
        text = (tmp_content / "post" / "hello-world" / "index.md").read_text()
        fm, body = parse(text)
        assert "gpg_sig" in fm
        assert "BEGIN PGP SIGNATURE" in fm["gpg_sig"]


class TestStripAllFields:
    def test_strip_removes_all_three_fields(self, tmp_content):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["gpg_sig"] = "fake-sig"
        fm["gpg_sig_date"] = "2026-01-15T12:00:00Z"
        fm["gpg_body_hash"] = "sha256:abc123"
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(main, ["strip", str(md_file)])
        assert result.exit_code == 0
        fm2, _ = parse(md_file.read_text())
        assert "gpg_sig" not in fm2
        assert "gpg_sig_date" not in fm2
        assert "gpg_body_hash" not in fm2

    def test_strip_partial_fields(self, tmp_content):
        """Strip works even if only some signing fields are present."""
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        fm, body = parse(md_file.read_text())
        fm["gpg_body_hash"] = "sha256:abc123"
        md_file.write_text(markdown.render(fm, body))
        runner = CliRunner()
        result = runner.invoke(main, ["strip", str(md_file)])
        assert result.exit_code == 0
        fm2, _ = parse(md_file.read_text())
        assert "gpg_body_hash" not in fm2


class TestVerifyNoFiles:
    def test_verify_no_files_exits_nonzero(self, tmp_path):
        """verify should exit 1 when no markdown files are found."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        runner = CliRunner()
        result = runner.invoke(main, ["verify", str(empty_dir)])
        assert result.exit_code == 1
        assert "no markdown files found" in result.output.lower()


class TestSignAllErrors:
    def test_sign_all_errors_exits_nonzero(self, tmp_path):
        """sign should exit 1 when all files error and none are signed."""
        md_file = tmp_path / "test.md"
        md_file.write_text("---\ntitle: Test\n---\nBody.\n")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["sign", "--key", "nonexistent-key@nowhere.invalid", str(md_file)],
        )
        assert result.exit_code == 1


class TestStatusJsonErrorCount:
    def test_status_json_reports_errors(self, tmp_path, gpg_home):
        """A file with malformed YAML produces an 'error' entry in --json output."""
        good = tmp_path / "good.md"
        good.write_text("---\ntitle: Good\n---\nOK.\n")
        bad = tmp_path / "bad.md"
        bad.write_text("---\ntitle: [unterminated\n  bad: indent\n---\nBody.\n")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["status", "--json", "--gpg-home", str(gpg_home), str(tmp_path)],
        )
        assert result.exit_code == 0
        # result.output mixes stderr (Rich error line) and stdout (JSON); slice from `{`
        data = json.loads(result.output[result.output.index("{") :])
        assert data["error"] >= 1
        assert data["total"] == (
            data["signed"] + data["unsigned"] + data["stale"] + data["invalid"] + data["error"]
        )


class TestWkdCommand:
    def test_writes_well_known_structure(self, tmp_path, gpg_home):
        """`sigmark wkd <dir>` populates .well-known/openpgpkey/ correctly."""
        out = tmp_path / "static"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "wkd",
                "--email",
                "test@example.com",
                "--gpg-home",
                str(gpg_home),
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        wkd_dir = out / ".well-known" / "openpgpkey"
        assert (wkd_dir / "policy").is_file()
        hu_files = list((wkd_dir / "hu").iterdir())
        assert len(hu_files) == 1
        assert hu_files[0].stat().st_size > 100  # pubkey is non-empty

    def test_missing_key_exits_nonzero(self, tmp_path):
        """No secret keys in the gnupg home → clean error, exit 1."""
        empty_home = tmp_path / "empty-gnupg"
        empty_home.mkdir(mode=0o700)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["wkd", "--gpg-home", str(empty_home), str(tmp_path / "out")],
        )
        assert result.exit_code == 1


class TestLongPathNotWrapped:
    def test_dry_run_does_not_wrap_long_paths(self, tmp_path):
        """Rich console must not wrap long file paths when output is redirected.

        CliRunner captures stdout/stderr as StringIO (non-TTY), which triggers
        rich's default 80-col wrapping. soft_wrap=True suppresses this so
        downstream tools (grep, awk, jq) see whole paths on one line.
        """
        deep = tmp_path / "a" / "very" / "deeply" / "nested" / "directory" / "structure"
        deep.mkdir(parents=True)
        md = deep / "a-file-with-a-fairly-long-name-exceeding-eighty-characters.md"
        md.write_text("---\ntitle: Deep\n---\nBody.\n")
        assert len(str(md)) > 80, "test path is not actually long enough"
        runner = CliRunner()
        result = runner.invoke(main, ["-n", "sign", str(md)])
        assert result.exit_code == 0
        assert any(
            "Would sign:" in line and str(md) in line
            for line in result.output.splitlines()
        ), f"Long path was wrapped in output:\n{result.output}"


class TestStripErrorHandling:
    def test_strip_continues_past_errored_file(self, tmp_path):
        """One unreadable file shouldn't abort a strip batch."""
        good = tmp_path / "good.md"
        fm_sig = (
            "---\ntitle: Good\ngpg_sig: fake\ngpg_sig_date: x\ngpg_body_hash: y\n"
            "---\nBody.\n"
        )
        good.write_text(fm_sig)
        bad = tmp_path / "bad.md"
        bad.write_text("---\ntitle: [unterminated\n---\nBody.\n")
        runner = CliRunner()
        result = runner.invoke(main, ["strip", str(tmp_path)])
        assert result.exit_code == 0
        # Good file should still be stripped even though bad file errored
        fm2, _ = parse(good.read_text())
        assert "gpg_sig" not in fm2
