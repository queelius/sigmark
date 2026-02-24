"""Shared test fixtures for sigmark."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_content(tmp_path: Path) -> Path:
    """Create a temporary content directory with sample .md files."""
    post = tmp_path / "post" / "hello-world"
    post.mkdir(parents=True)
    (post / "index.md").write_text(
        "---\ntitle: Hello World\ndate: 2026-01-01\ntags:\n  - test\n---\n"
        "This is the body of the post.\n\nIt has multiple paragraphs.\n"
    )
    post2 = tmp_path / "post" / "second-post"
    post2.mkdir(parents=True)
    (post2 / "index.md").write_text(
        "---\ntitle: Second Post\ndate: 2026-01-02\n---\nAnother post body.\n"
    )
    (tmp_path / "README.md").write_text("# Just a readme\n\nNo front matter here.\n")
    return tmp_path


@pytest.fixture
def gpg_home(tmp_path: Path) -> Path:
    """Create a temporary GPG home with a test key."""
    gnupg_dir = tmp_path / ".gnupg"
    gnupg_dir.mkdir(mode=0o700)
    key_params = gnupg_dir / "key_params"
    key_params.write_text(
        "%no-protection\n"
        "Key-Type: RSA\n"
        "Key-Length: 2048\n"
        "Name-Real: Test Signer\n"
        "Name-Email: test@example.com\n"
        "Expire-Date: 0\n"
        "%commit\n"
    )
    env = {**os.environ, "GNUPGHOME": str(gnupg_dir)}
    subprocess.run(
        ["gpg", "--batch", "--gen-key", str(key_params)],
        env=env,
        capture_output=True,
        check=True,
    )
    return gnupg_dir
