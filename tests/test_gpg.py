"""Tests for sigmark.gpg module."""

from __future__ import annotations

import pytest

from sigmark.gpg import sign, verify


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
