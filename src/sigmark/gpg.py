"""GPG signing and verification via subprocess."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@contextmanager
def _temp_text(content: str, suffix: str) -> Iterator[str]:
    """Write ``content`` to a tempfile (UTF-8), yield its path, always unlink it."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        path = f.name
    try:
        yield path
    finally:
        Path(path).unlink(missing_ok=True)


def sign(body: str, key: str | None = None, gpg_home: Path | None = None) -> str:
    """Produce an ASCII-armored detached GPG signature of body text.

    If *key* is ``None``, GPG uses its default key.
    Raises RuntimeError if GPG fails.
    """
    env = _gpg_env(gpg_home)
    with _temp_text(body, ".txt") as body_path:
        sig_path = Path(body_path + ".asc")
        try:
            cmd = ["gpg", "--batch", "--yes", "--armor", "--detach-sign"]
            if key is not None:
                cmd.extend(["--local-user", key])
            cmd.append(body_path)
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                raise RuntimeError(f"GPG sign failed: {result.stderr.strip()}")
            return sig_path.read_text(encoding="utf-8")
        finally:
            sig_path.unlink(missing_ok=True)


@dataclass
class VerifyResult:
    """Result of a GPG signature verification."""

    valid: bool
    key_id: str | None = None
    error: str | None = None


def verify(body: str, signature: str, gpg_home: Path | None = None) -> VerifyResult:
    """Verify a detached GPG signature against body text."""
    env = _gpg_env(gpg_home)
    with _temp_text(body, ".txt") as body_path, _temp_text(signature, ".sig") as sig_path:
        result = subprocess.run(
            ["gpg", "--batch", "--verify", sig_path, body_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return VerifyResult(valid=True, key_id=_extract_key_id(result.stderr))
        return VerifyResult(valid=False, error=result.stderr.strip())


def _extract_key_id(stderr: str) -> str | None:
    """Extract key ID from GPG verify output."""
    match = re.search(r"using \w+ key ([0-9A-F]+)", stderr)
    return match.group(1) if match else None


def _gpg_env(gpg_home: Path | None) -> dict[str, str] | None:
    """Build environment dict with GNUPGHOME if provided."""
    if gpg_home is None:
        return None
    return {**os.environ, "GNUPGHOME": str(gpg_home)}
