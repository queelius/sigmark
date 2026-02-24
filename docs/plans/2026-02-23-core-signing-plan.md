# Core Signing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement GPG signing/verification of markdown file bodies with signatures stored in YAML front matter, exposed via four CLI subcommands.

**Architecture:** Three modules — `markdown.py` (parse/render front matter + body, resolve file paths), `gpg.py` (sign/verify via GPG subprocess), `cli.py` (Click subcommands wiring the two together). TDD throughout.

**Tech Stack:** Python 3.10+, Click, PyYAML, Rich, pytest, GPG subprocess

**Design doc:** `docs/plans/2026-02-23-core-signing-design.md`

---

### Task 1: markdown.parse — split front matter from body

**Files:**
- Create: `tests/test_markdown.py`
- Create: `src/sigmark/markdown.py`

**Step 1: Write failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_markdown.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sigmark.markdown'`

**Step 3: Write minimal implementation**

```python
"""Markdown front matter parsing and rendering."""
from __future__ import annotations

import re

import yaml


def parse(text: str) -> tuple[dict, str]:
    """Split markdown into (front_matter_dict, body_str).

    Front matter is delimited by opening and closing ``---`` lines.
    Body is everything after the closing delimiter.
    Raises ValueError if no front matter is found.
    """
    match = re.match(r"\A---\n(.*?)^---\n(.*)\Z", text, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError("No YAML front matter found")
    fm_raw, body = match.group(1), match.group(2)
    front_matter = yaml.safe_load(fm_raw) or {}
    return front_matter, body
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_markdown.py -v`
Expected: all 6 PASS

**Step 5: Commit**

```bash
git add tests/test_markdown.py src/sigmark/markdown.py
git commit -m "feat: add markdown.parse for front matter splitting"
```

---

### Task 2: markdown.render — reassemble front matter + body

**Files:**
- Modify: `tests/test_markdown.py`
- Modify: `src/sigmark/markdown.py`

**Step 1: Write failing tests**

Append to `tests/test_markdown.py`:

```python
from sigmark.markdown import render


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_markdown.py::TestRender -v`
Expected: FAIL — `cannot import name 'render'`

**Step 3: Write minimal implementation**

Append to `src/sigmark/markdown.py`:

```python
def render(front_matter: dict, body: str) -> str:
    """Reassemble front matter dict and body into a markdown string."""
    if front_matter:
        fm_str = yaml.dump(front_matter, default_flow_style=False, sort_keys=False)
    else:
        fm_str = ""
    return f"---\n{fm_str}---\n{body}"
```

**Step 4: Run all markdown tests**

Run: `pytest tests/test_markdown.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_markdown.py src/sigmark/markdown.py
git commit -m "feat: add markdown.render for reassembly"
```

---

### Task 3: markdown.resolve_paths — expand files/dirs to .md list

**Files:**
- Modify: `tests/test_markdown.py`
- Modify: `src/sigmark/markdown.py`

**Step 1: Write failing tests**

Append to `tests/test_markdown.py`:

```python
from pathlib import Path

from sigmark.markdown import resolve_paths


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_markdown.py::TestResolvePaths -v`
Expected: FAIL — `cannot import name 'resolve_paths'`

**Step 3: Write minimal implementation**

Append to `src/sigmark/markdown.py`:

```python
from pathlib import Path


def resolve_paths(paths: list[Path]) -> list[Path]:
    """Expand files and directories into a list of .md files with front matter.

    Directories are walked recursively. Individual files are validated
    to have front matter. Raises FileNotFoundError for missing paths
    and ValueError for files without front matter.
    """
    result: list[Path] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if path.is_file():
            # Validate it has front matter
            parse(path.read_text())
            result.append(path)
        elif path.is_dir():
            for md_file in sorted(path.rglob("*.md")):
                try:
                    parse(md_file.read_text())
                    result.append(md_file)
                except ValueError:
                    continue  # skip .md files without front matter
    return result
```

**Step 4: Run all markdown tests**

Run: `pytest tests/test_markdown.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_markdown.py src/sigmark/markdown.py
git commit -m "feat: add markdown.resolve_paths for file/dir expansion"
```

---

### Task 4: gpg.sign — produce detached signature

**Files:**
- Create: `tests/test_gpg.py`
- Create: `src/sigmark/gpg.py`

**Step 1: Write failing tests**

```python
"""Tests for sigmark.gpg module."""
from __future__ import annotations

from sigmark.gpg import sign


class TestSign:
    def test_produces_ascii_armored_signature(self, gpg_home):
        sig = sign("Hello world.\n", key="test@example.com", gpg_home=gpg_home)
        assert "-----BEGIN PGP SIGNATURE-----" in sig
        assert "-----END PGP SIGNATURE-----" in sig

    def test_different_content_produces_different_signature(self, gpg_home):
        sig1 = sign("Content A.\n", key="test@example.com", gpg_home=gpg_home)
        sig2 = sign("Content B.\n", key="test@example.com", gpg_home=gpg_home)
        assert sig1 != sig2

    def test_bad_key_raises(self, gpg_home):
        with pytest.raises(RuntimeError, match="GPG sign failed"):
            sign("Hello.\n", key="nonexistent@example.com", gpg_home=gpg_home)


import pytest
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gpg.py::TestSign -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sigmark.gpg'`

**Step 3: Write minimal implementation**

```python
"""GPG signing and verification via subprocess."""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


def sign(body: str, key: str, gpg_home: Path | None = None) -> str:
    """Produce an ASCII-armored detached GPG signature of body text.

    Raises RuntimeError if GPG fails.
    """
    env = _gpg_env(gpg_home)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(body)
        f.flush()
        body_path = f.name
    try:
        result = subprocess.run(
            [
                "gpg", "--batch", "--yes", "--armor", "--detach-sign",
                "--local-user", key, body_path,
            ],
            env=env, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GPG sign failed: {result.stderr.strip()}")
        sig_path = Path(body_path + ".asc")
        return sig_path.read_text()
    finally:
        Path(body_path).unlink(missing_ok=True)
        Path(body_path + ".asc").unlink(missing_ok=True)


def _gpg_env(gpg_home: Path | None) -> dict[str, str] | None:
    """Build environment dict with GNUPGHOME if provided."""
    if gpg_home is None:
        return None
    import os
    return {**os.environ, "GNUPGHOME": str(gpg_home)}
```

**Step 4: Run tests**

Run: `pytest tests/test_gpg.py::TestSign -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_gpg.py src/sigmark/gpg.py
git commit -m "feat: add gpg.sign for detached GPG signatures"
```

---

### Task 5: gpg.verify — check detached signature

**Files:**
- Modify: `tests/test_gpg.py`
- Modify: `src/sigmark/gpg.py`

**Step 1: Write failing tests**

Append to `tests/test_gpg.py`:

```python
from sigmark.gpg import verify


class TestVerify:
    def test_valid_signature(self, gpg_home):
        body = "Hello world.\n"
        sig = sign(body, key="test@example.com", gpg_home=gpg_home)
        result = verify(body, sig, gpg_home=gpg_home)
        assert result.valid is True
        assert result.key_id is not None
        assert result.error is None

    def test_tampered_body_fails(self, gpg_home):
        sig = sign("Original.\n", key="test@example.com", gpg_home=gpg_home)
        result = verify("Tampered.\n", sig, gpg_home=gpg_home)
        assert result.valid is False
        assert result.error is not None

    def test_garbage_signature_fails(self, gpg_home):
        result = verify("Hello.\n", "not-a-signature", gpg_home=gpg_home)
        assert result.valid is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gpg.py::TestVerify -v`
Expected: FAIL — `cannot import name 'verify'`

**Step 3: Write minimal implementation**

Append to `src/sigmark/gpg.py`:

```python
@dataclass
class VerifyResult:
    """Result of a GPG signature verification."""
    valid: bool
    key_id: str | None = None
    error: str | None = None


def verify(body: str, signature: str, gpg_home: Path | None = None) -> VerifyResult:
    """Verify a detached GPG signature against body text."""
    env = _gpg_env(gpg_home)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as bf:
        bf.write(body)
        bf.flush()
        body_path = bf.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sig", delete=False) as sf:
        sf.write(signature)
        sf.flush()
        sig_path = sf.name
    try:
        result = subprocess.run(
            ["gpg", "--batch", "--verify", sig_path, body_path],
            env=env, capture_output=True, text=True,
        )
        if result.returncode == 0:
            key_id = _extract_key_id(result.stderr)
            return VerifyResult(valid=True, key_id=key_id)
        return VerifyResult(valid=False, error=result.stderr.strip())
    finally:
        Path(body_path).unlink(missing_ok=True)
        Path(sig_path).unlink(missing_ok=True)


def _extract_key_id(stderr: str) -> str | None:
    """Extract key ID from GPG verify output."""
    import re
    match = re.search(r"using \w+ key ([0-9A-F]+)", stderr)
    return match.group(1) if match else None
```

**Step 4: Run all GPG tests**

Run: `pytest tests/test_gpg.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_gpg.py src/sigmark/gpg.py
git commit -m "feat: add gpg.verify for signature verification"
```

---

### Task 6: CLI sign subcommand

**Files:**
- Create: `tests/test_cli.py`
- Modify: `src/sigmark/cli.py`

**Step 1: Write failing tests**

```python
"""Tests for sigmark CLI subcommands."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestSignCommand -v`
Expected: FAIL — `No such command 'sign'`

**Step 3: Write implementation**

Replace `src/sigmark/cli.py` contents:

```python
"""sigmark CLI entry point."""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from sigmark import __version__
from sigmark import gpg, markdown

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="sigmark")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("-n", "--dry-run", is_flag=True, help="Preview without making changes")
@click.pass_context
def main(ctx: click.Context, verbose: bool, dry_run: bool) -> None:
    """GPG signing for static site markdown content."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run


@main.command()
@click.option("--key", required=True, help="GPG key ID or email for signing")
@click.option("--gpg-home", type=click.Path(exists=True, path_type=Path), default=None, hidden=True,
              help="Custom GPG home directory (for testing)")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def sign(ctx: click.Context, key: str, gpg_home: Path | None, paths: tuple[Path, ...]) -> None:
    """Sign markdown files with GPG."""
    dry_run = ctx.obj["dry_run"]
    verbose = ctx.obj["verbose"]
    files = markdown.resolve_paths(list(paths))
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        sig = gpg.sign(body, key=key, gpg_home=gpg_home)
        fm["signature"] = sig
        if dry_run:
            console.print(f"[yellow]Would sign:[/yellow] {md_file}")
        else:
            md_file.write_text(markdown.render(fm, body))
            console.print(f"[green]Signed:[/green] {md_file}")
```

**Step 4: Run tests**

Run: `pytest tests/test_cli.py::TestSignCommand -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_cli.py src/sigmark/cli.py
git commit -m "feat: add sign CLI subcommand"
```

---

### Task 7: CLI verify subcommand

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/sigmark/cli.py`

**Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
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
        assert "valid" in result.output.lower() or "PASS" in result.output or "✓" in result.output

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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestVerifyCommand -v`
Expected: FAIL — `No such command 'verify'`

**Step 3: Write implementation**

Append to `src/sigmark/cli.py`:

```python
@main.command()
@click.option("--gpg-home", type=click.Path(exists=True, path_type=Path), default=None, hidden=True)
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def verify(ctx: click.Context, gpg_home: Path | None, paths: tuple[Path, ...]) -> None:
    """Verify GPG signatures on markdown files."""
    verbose = ctx.obj["verbose"]
    files = markdown.resolve_paths(list(paths))
    all_valid = True
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        sig = fm.get("signature")
        if not sig:
            console.print(f"[red]Unsigned:[/red] {md_file}")
            all_valid = False
            continue
        result = gpg.verify(body, sig, gpg_home=gpg_home)
        if result.valid:
            console.print(f"[green]Valid:[/green] {md_file}")
        else:
            console.print(f"[red]Invalid:[/red] {md_file}")
            if verbose and result.error:
                console.print(f"  {result.error}")
            all_valid = False
    if not all_valid:
        raise SystemExit(1)
```

**Step 4: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_cli.py src/sigmark/cli.py
git commit -m "feat: add verify CLI subcommand"
```

---

### Task 8: CLI strip subcommand

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/sigmark/cli.py`

**Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
class TestStripCommand:
    def test_strip_removes_signature(self, tmp_content, gpg_home):
        md_file = tmp_content / "post" / "hello-world" / "index.md"
        # Sign first
        fm, body = parse(md_file.read_text())
        fm["signature"] = "fake-sig"
        md_file.write_text(markdown.render(fm, body))
        # Strip
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestStripCommand -v`
Expected: FAIL — `No such command 'strip'`

**Step 3: Write implementation**

Append to `src/sigmark/cli.py`:

```python
@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def strip(ctx: click.Context, paths: tuple[Path, ...]) -> None:
    """Remove GPG signatures from markdown files."""
    dry_run = ctx.obj["dry_run"]
    files = markdown.resolve_paths(list(paths))
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        if "signature" not in fm:
            continue
        del fm["signature"]
        if dry_run:
            console.print(f"[yellow]Would strip:[/yellow] {md_file}")
        else:
            md_file.write_text(markdown.render(fm, body))
            console.print(f"[green]Stripped:[/green] {md_file}")
```

**Step 4: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_cli.py src/sigmark/cli.py
git commit -m "feat: add strip CLI subcommand"
```

---

### Task 9: CLI status subcommand

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/sigmark/cli.py`

**Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
from sigmark import gpg


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestStatusCommand -v`
Expected: FAIL — `No such command 'status'`

**Step 3: Write implementation**

Append to `src/sigmark/cli.py`:

```python
@main.command()
@click.option("--gpg-home", type=click.Path(exists=True, path_type=Path), default=None, hidden=True)
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def status(ctx: click.Context, gpg_home: Path | None, paths: tuple[Path, ...]) -> None:
    """Report signing status of markdown files."""
    files = markdown.resolve_paths(list(paths))
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        sig = fm.get("signature")
        if not sig:
            console.print(f"[dim]Unsigned:[/dim] {md_file}")
            continue
        result = gpg.verify(body, sig, gpg_home=gpg_home)
        if result.valid:
            console.print(f"[green]Valid:[/green] {md_file}")
        else:
            console.print(f"[red]Invalid:[/red] {md_file}")
```

**Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add tests/test_cli.py src/sigmark/cli.py
git commit -m "feat: add status CLI subcommand"
```

---

### Task 10: Full test coverage check and CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Run coverage**

Run: `pytest --cov=sigmark --cov-report=term-missing tests/`
Review output for uncovered lines.

**Step 2: Run linter and type checker**

Run: `ruff check src/ tests/ && mypy src/sigmark/`

**Step 3: Fix any issues found**

Address uncovered lines, lint errors, or type errors.

**Step 4: Update CLAUDE.md**

Add the new modules to the architecture section.

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: update CLAUDE.md and fix lint/coverage gaps"
```
