"""Web Key Directory (WKD) support for publishing GPG pubkeys.

Implements the 'direct method' from draft-koch-openpgp-webkey-service-14:

    https://<domain>/.well-known/openpgpkey/policy
    https://<domain>/.well-known/openpgpkey/hu/<zbase32-sha1-of-local-part>

Drop the generated output directory into your static-site's web root, and
the pubkey becomes discoverable via ``gpg --locate-keys <email>``.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

# Zooko's base32 alphabet (not RFC 4648). 5 bits per character.
_ZBASE32_ALPHABET = "ybndrfg8ejkmcpqxot1uwisza345h769"


def _zbase32_encode(data: bytes) -> str:
    """Encode ``data`` using zbase32.

    Each 5-bit group maps to one character of the zbase32 alphabet.
    A 20-byte SHA-1 (160 bits) encodes to exactly 32 characters.
    """
    bits = "".join(f"{b:08b}" for b in data)
    pad = (-len(bits)) % 5
    bits += "0" * pad
    return "".join(_ZBASE32_ALPHABET[int(bits[i : i + 5], 2)] for i in range(0, len(bits), 5))


def wkd_hash(local_part: str) -> str:
    """Compute the WKD hash for an email local-part.

    Spec: zbase32(sha1(lowercase(local-part))).
    For example ``wkd_hash("lex") == "483zgkw4pjsii3ba8n8b5hosjxpumw5t"``.
    """
    digest = hashlib.sha1(local_part.lower().encode("utf-8")).digest()  # noqa: S324
    return _zbase32_encode(digest)


def _gpg_env(gpg_home: Path | None) -> dict[str, str] | None:
    if gpg_home is None:
        return None
    return {**os.environ, "GNUPGHOME": str(gpg_home)}


def export_pubkey(selector: str, gpg_home: Path | None = None) -> bytes:
    """Export a binary (non-armored) pubkey via gpg.

    ``selector`` may be an email, fingerprint, key ID, or user ID substring.
    Raises RuntimeError if gpg fails or returns no data.
    """
    result = subprocess.run(
        ["gpg", "--export", "--no-armor", selector],
        env=_gpg_env(gpg_home),
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"GPG export failed for {selector!r}: {stderr}")
    return result.stdout


def find_default_email(selector: str | None = None, gpg_home: Path | None = None) -> str:
    """Return the primary email UID of a secret key.

    If ``selector`` is given, look up that specific key; otherwise use the
    only secret key in the keyring. Raises RuntimeError if zero or multiple
    secret keys exist and none was specified, or if no email UID is found.
    """
    cmd = ["gpg", "--list-secret-keys", "--with-colons"]
    if selector is not None:
        cmd.append(selector)
    result = subprocess.run(
        cmd, env=_gpg_env(gpg_home), capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(f"gpg --list-secret-keys failed: {result.stderr.strip()}")

    # Parse colon-separated output. We want 'uid:' lines under 'sec:' blocks.
    # When no selector is given and multiple secret keys exist, this is ambiguous.
    sec_blocks: list[list[str]] = []
    current: list[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("sec:"):
            if current:
                sec_blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        sec_blocks.append(current)

    if not sec_blocks:
        raise RuntimeError("No secret keys found in keyring.")
    if len(sec_blocks) > 1 and selector is None:
        raise RuntimeError(
            f"Multiple secret keys found ({len(sec_blocks)}). Specify one with --key."
        )

    for line in sec_blocks[0]:
        if line.startswith("uid:"):
            uid = line.split(":")[9]
            match = re.search(r"<([^>]+@[^>]+)>", uid)
            if match:
                return match.group(1)
    raise RuntimeError("No email address found in key UIDs.")


def install(output_dir: Path, email: str, gpg_home: Path | None = None) -> Path:
    """Write WKD files into ``<output_dir>/.well-known/openpgpkey/``.

    Creates:
        <output_dir>/.well-known/openpgpkey/policy               (empty)
        <output_dir>/.well-known/openpgpkey/hu/<wkd_hash>        (binary pubkey)

    Returns the path to the written pubkey file. Overwrites any existing
    WKD files at the target paths.
    """
    if "@" not in email:
        raise ValueError(f"Not an email address: {email!r}")
    local_part = email.split("@", 1)[0]

    wkd_dir = output_dir / ".well-known" / "openpgpkey"
    hu_dir = wkd_dir / "hu"
    hu_dir.mkdir(parents=True, exist_ok=True)

    # Empty policy file signals default policy to WKD clients.
    (wkd_dir / "policy").write_bytes(b"")

    pubkey_binary = export_pubkey(email, gpg_home=gpg_home)
    pubkey_path = hu_dir / wkd_hash(local_part)
    pubkey_path.write_bytes(pubkey_binary)
    return pubkey_path
