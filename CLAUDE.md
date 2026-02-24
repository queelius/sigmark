# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

sigmark — GPG signing for static site markdown content. Python CLI tool that signs Hugo/static-site markdown files with GPG, embedding or managing signatures alongside content.

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

- **`src/sigmark/`** — main package (src-layout, built with hatchling)
  - `cli.py` — Click-based CLI entry point (`sigmark` command). Uses `click.group()` with `--verbose` and `--dry-run` global options; subcommands (`sign`, `verify`, `strip`, `status`) share state via `ctx.obj`
  - `markdown.py` — front-matter parsing (`parse`/`render`) and file discovery (`resolve_paths`). Uses a custom `_StringDateLoader` to keep YAML dates as strings for faithful round-tripping.
  - `gpg.py` — GPG operations via subprocess: `sign()` produces ASCII-armored detached signatures, `verify()` returns a `VerifyResult` dataclass. Both accept optional `gpg_home` for test isolation.
  - `__init__.py` — package metadata (`__version__`)
- **`tests/`** — pytest test suite
  - `conftest.py` — shared fixtures: `tmp_content` (sample Hugo content tree with front-matter markdown) and `gpg_home` (ephemeral GPG keyring with a test key)

## Design

Signatures are stored as a `signature` field in YAML front matter. Only the body (below the closing `---`) is signed — front matter is excluded. The signing key must be specified explicitly via `--key`. All subcommands accept files and/or directories as `PATHS` arguments.

## Key Conventions

- Python >=3.10, uses `from __future__ import annotations`
- Ruff for linting/formatting (line-length 100, rules: E/F/I/N/W/UP/B/C4/SIM)
- CLI built on Click; Rich for terminal output; PyYAML for front-matter parsing
- Test GPG operations use isolated `GNUPGHOME` via the `gpg_home` fixture — never touches real keyring
- Content fixtures model Hugo page bundles: `post/<slug>/index.md` with YAML front matter
