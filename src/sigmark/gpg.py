"""GPG signing and verification via subprocess."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


def sign(body: str, key: str | None = None, gpg_home: Path | None = None) -> str:
    """Produce an ASCII-armored detached GPG signature of body text.

    If *key* is ``None``, GPG uses its default key.
    Raises RuntimeError if GPG fails.
    """
    env = _gpg_env(gpg_home)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(body)
        f.flush()
        body_path = f.name
    try:
        cmd = [
            "gpg",
            "--batch",
            "--yes",
            "--armor",
            "--detach-sign",
        ]
        if key is not None:
            cmd.extend(["--local-user", key])
        cmd.append(body_path)
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GPG sign failed: {result.stderr.strip()}")
        sig_path = Path(body_path + ".asc")
        return sig_path.read_text()
    finally:
        Path(body_path).unlink(missing_ok=True)
        Path(body_path + ".asc").unlink(missing_ok=True)


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
            env=env,
            capture_output=True,
            text=True,
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
    match = re.search(r"using \w+ key ([0-9A-F]+)", stderr)
    return match.group(1) if match else None


def _gpg_env(gpg_home: Path | None) -> dict[str, str] | None:
    """Build environment dict with GNUPGHOME if provided."""
    if gpg_home is None:
        return None
    return {**os.environ, "GNUPGHOME": str(gpg_home)}
