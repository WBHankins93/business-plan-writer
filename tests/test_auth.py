import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from web_api.auth import SupabaseTokenVerifier


class SupabaseTokenVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_key = cls.private_key.public_key()

    def verifier(self):
        verifier = SupabaseTokenVerifier(
            supabase_url="https://project.supabase.co",
            publishable_key="publishable-test-key",
        )
        verifier.jwks.get_signing_key_from_jwt = lambda _token: SimpleNamespace(
            key=self.public_key
        )
        return verifier

    def token(self, **overrides):
        now = datetime.now(UTC)
        claims = {
            "sub": "user-a",
            "email": "a@example.com",
            "role": "authenticated",
            "aud": "authenticated",
            "iss": "https://project.supabase.co/auth/v1",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    def test_valid_supabase_access_token_returns_subject(self):
        user = self.verifier().verify(self.token())
        self.assertEqual(user.id, "user-a")
        self.assertEqual(user.email, "a@example.com")

    def test_expired_token_is_rejected_with_expired_session_code(self):
        with self.assertRaises(HTTPException) as caught:
            self.verifier().verify(self.token(exp=datetime.now(UTC) - timedelta(seconds=1)))
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(caught.exception.detail["code"], "session_expired")

    def test_wrong_issuer_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            self.verifier().verify(self.token(iss="https://attacker.example/auth/v1"))
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(caught.exception.detail["code"], "invalid_session")

    def test_legacy_hs256_uses_auth_server_instead_of_shared_secret(self):
        token = jwt.encode(
            {"sub": "user-a"}, "not-a-server-secret", algorithm="HS256"
        )
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {"id": "user-a", "email": "a@example.com"},
        )
        with patch("web_api.auth.httpx.get", return_value=response) as get:
            user = self.verifier().verify(token)
        self.assertEqual(user.id, "user-a")
        self.assertEqual(get.call_args.kwargs["headers"]["apikey"], "publishable-test-key")


if __name__ == "__main__":
    unittest.main()
