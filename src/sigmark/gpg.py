"""GPG signing and verification via subprocess."""
from __future__ import annotations

import os
import subprocess
import tempfile
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
                "gpg",
                "--batch",
                "--yes",
                "--armor",
                "--detach-sign",
                "--local-user",
                key,
                body_path,
            ],
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


def _gpg_env(gpg_home: Path | None) -> dict[str, str] | None:
    """Build environment dict with GNUPGHOME if provided."""
    if gpg_home is None:
        return None
    return {**os.environ, "GNUPGHOME": str(gpg_home)}
