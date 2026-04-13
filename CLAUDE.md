# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

sigmark: GPG signing for static site markdown content. Python CLI tool that signs Hugo/static-site markdown files with GPG, embedding or managing signatures alongside content.

## Build & Development

```bash
# Install in editable mode with dev deps
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file or test
pytest tests/test_foo.py
pytest tests/test_foo.py::test_bar

# Test coverage
pytest --cov=sigmark --cov-report=term-missing

# Lint
ruff check src/ tests/
ruff format --check src/ tests/

# Type check
mypy src/sigmark/
```

## Architecture

- **`src/sigmark/`**: main package (src-layout, built with hatchling)
  - `cli.py`: Click-based CLI entry point (`sigmark` command). `click.group()` with `--verbose` and `--dry-run` global options; subcommands `sign`/`verify`/`strip`/`status` share state via `ctx.obj`. Shared helpers: `gpg_home_option` decorator, `_load_files` default-path wrapper, `SIG_FIELDS` constant, `_STATUS_STYLES` dict that drives both human and JSON output.
  - `markdown.py`: front-matter parsing (`parse`/`render`), hashing (`compute_body_hash`), and file discovery (`load_files`). `load_files` returns a plain `list[Path]` with a cheap header sniff (reads the first line) to filter out non-front-matter files in directory walks; callers do the full parse themselves in their own try/except. Uses `ruamel.yaml` (not PyYAML) with `preserve_quotes=True` and `width=4096` to round-trip signatures without line-wrapping; timestamp resolvers are stripped from both `_version_implicit_resolver` and `versioned_resolver` so dates stay as strings.
  - `gpg.py`: GPG operations via subprocess. `sign()` produces ASCII-armored detached signatures, `verify()` returns a `VerifyResult` dataclass. Both accept optional `gpg_home` for test isolation. Tempfiles are wrapped in a `_temp_text` context manager so cleanup is guaranteed even if a second tempfile ctor raises.
  - `__init__.py`: package metadata (`__version__` via `importlib.metadata`)
- **`tests/`**: pytest test suite
  - `conftest.py`: shared fixtures. `tmp_content` (sample Hugo content tree with front-matter markdown) and `gpg_home` (ephemeral GPG keyring with a test key)

## Design

Signatures are stored as three fields in YAML front matter: `gpg_sig` (the ASCII-armored signature), `gpg_sig_date` (ISO-8601 UTC timestamp), and `gpg_body_hash` (SHA-256 of the normalized body, used for fast staleness detection). Only the body (below the closing `---`) is signed; front matter is excluded. The body is normalized (per-line `rstrip`, single trailing `\n`) before signing and hashing so reproducibility doesn't depend on editor quirks. The signing key is optional (`--key`); GPG's default key is used when omitted.

Rich console output goes to stderr; `click.echo` output (e.g. `status --json`) goes to stdout, so pipes like `sigmark status --json content/ | jq` work cleanly.

## Key Conventions

- Python >=3.10, uses `from __future__ import annotations`
- Ruff for linting/formatting (line-length 100, rules: E/F/I/N/W/UP/B/C4/SIM)
- CLI built on Click; Rich for terminal output; `ruamel.yaml` for front-matter parsing
- Test GPG operations use isolated `GNUPGHOME` via the `gpg_home` fixture, never touches real keyring
- Content fixtures model Hugo page bundles: `post/<slug>/index.md` with YAML front matter
