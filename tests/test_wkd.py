"""Tests for sigmark.wkd module."""

from __future__ import annotations

import subprocess

import pytest

from sigmark.wkd import _zbase32_encode, export_pubkey, find_default_email, install, wkd_hash


class TestZbase32:
    def test_encode_empty(self):
        assert _zbase32_encode(b"") == ""

    def test_encode_known_vector(self):
        # "lex" SHA-1 → known hash computed by gpg --with-wkd-hash.
        # This is the canonical test vector binding our impl to gpg's output.
        assert wkd_hash("lex") == "483zgkw4pjsii3ba8n8b5hosjxpumw5t"

    def test_hash_is_case_insensitive(self):
        assert wkd_hash("Lex") == wkd_hash("lex") == wkd_hash("LEX")

    def test_hash_length(self):
        # SHA-1 is 160 bits; zbase32 at 5 bits/char → exactly 32 characters.
        assert len(wkd_hash("whatever")) == 32

    def test_different_local_parts_differ(self):
        assert wkd_hash("alice") != wkd_hash("bob")


class TestExportPubkey:
    def test_exports_binary_pubkey(self, gpg_home):
        data = export_pubkey("test@example.com", gpg_home=gpg_home)
        assert len(data) > 100  # pubkeys are hundreds of bytes minimum
        # Binary (non-armored) pubkey packets start with OpenPGP packet tag bytes,
        # not ASCII; assert it is NOT armored.
        assert b"BEGIN PGP PUBLIC KEY BLOCK" not in data

    def test_missing_key_raises(self, gpg_home):
        with pytest.raises(RuntimeError, match="GPG export failed"):
            export_pubkey("nobody@nowhere.invalid", gpg_home=gpg_home)


class TestFindDefaultEmail:
    def test_single_secret_key(self, gpg_home):
        email = find_default_email(gpg_home=gpg_home)
        assert email == "test@example.com"

    def test_selector_picks_specific_key(self, gpg_home):
        email = find_default_email(selector="test@example.com", gpg_home=gpg_home)
        assert email == "test@example.com"

    def test_no_keys_raises(self, tmp_path):
        empty_home = tmp_path / "empty-gnupg"
        empty_home.mkdir(mode=0o700)
        with pytest.raises(RuntimeError, match="No secret keys"):
            find_default_email(gpg_home=empty_home)


class TestInstall:
    def test_creates_expected_structure(self, tmp_path, gpg_home):
        out = tmp_path / "site-static"
        pubkey_path = install(out, "test@example.com", gpg_home=gpg_home)

        wkd_dir = out / ".well-known" / "openpgpkey"
        assert wkd_dir.is_dir()
        assert (wkd_dir / "policy").is_file()
        assert (wkd_dir / "policy").read_bytes() == b""
        assert pubkey_path.parent == wkd_dir / "hu"
        assert pubkey_path.is_file()
        assert pubkey_path.name == wkd_hash("test")

    def test_pubkey_matches_gpg_export(self, tmp_path, gpg_home):
        out = tmp_path / "site-static"
        pubkey_path = install(out, "test@example.com", gpg_home=gpg_home)

        # Independently export and compare.
        import os

        env = {**os.environ, "GNUPGHOME": str(gpg_home)}
        direct = subprocess.run(
            ["gpg", "--export", "--no-armor", "test@example.com"],
            env=env,
            capture_output=True,
            check=True,
        ).stdout
        assert pubkey_path.read_bytes() == direct

    def test_non_email_raises(self, tmp_path, gpg_home):
        with pytest.raises(ValueError, match="Not an email"):
            install(tmp_path, "not-an-email", gpg_home=gpg_home)

    def test_overwrites_existing(self, tmp_path, gpg_home):
        out = tmp_path / "site-static"
        pubkey_path = install(out, "test@example.com", gpg_home=gpg_home)
        first_bytes = pubkey_path.read_bytes()

        # Pre-populate with junk; install should overwrite.
        pubkey_path.write_bytes(b"stale garbage")
        install(out, "test@example.com", gpg_home=gpg_home)
        assert pubkey_path.read_bytes() == first_bytes
