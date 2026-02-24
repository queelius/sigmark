"""Tests for sigmark.gpg module."""
from __future__ import annotations

import pytest

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
