from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None


class SupabaseTokenVerifier:
    """Verify Supabase access tokens without any service-role credential."""

    def __init__(
        self,
        *,
        supabase_url: str | None = None,
        publishable_key: str | None = None,
    ) -> None:
        self.supabase_url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.publishable_key = publishable_key or os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
        if not self.supabase_url:
            raise RuntimeError("SUPABASE_URL must be configured for authenticated API routes.")
        self.issuer = f"{self.supabase_url}/auth/v1"
        self.jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", lifespan=300)

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm == "HS256":
                return self._verify_with_auth_server(token)
            if algorithm not in {"ES256", "RS256"}:
                raise jwt.InvalidAlgorithmError("Unsupported access-token algorithm")
            signing_key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm],
                audience="authenticated",
                issuer=self.issuer,
                options={"require": ["sub", "exp", "iss", "aud"]},
            )
            return _user_from_claims(claims)
        except jwt.ExpiredSignatureError as exc:
            raise _auth_error("session_expired", "Your session has expired. Sign in again.") from exc
        except HTTPException:
            raise
        except (jwt.PyJWTError, ValueError, httpx.HTTPError) as exc:
            raise _auth_error("invalid_session", "Your session is invalid. Sign in again.") from exc

    def _verify_with_auth_server(self, token: str) -> AuthenticatedUser:
        if not self.publishable_key:
            raise jwt.InvalidTokenError(
                "SUPABASE_PUBLISHABLE_KEY is required for legacy HS256 token validation"
            )
        response = httpx.get(
            f"{self.issuer}/user",
            headers={
                "apikey": self.publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=5.0,
        )
        if response.status_code != 200:
            raise jwt.InvalidTokenError("Supabase Auth rejected the access token")
        payload = response.json()
        user_id = payload.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise jwt.InvalidTokenError("Supabase Auth response did not include a user ID")
        email = payload.get("email")
        return AuthenticatedUser(id=user_id, email=email if isinstance(email, str) else None)


def _user_from_claims(claims: dict[str, Any]) -> AuthenticatedUser:
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise jwt.InvalidTokenError("Access token has no subject")
    if claims.get("role") not in {None, "authenticated"}:
        raise jwt.InvalidTokenError("Access token does not represent an authenticated user")
    email = claims.get("email")
    return AuthenticatedUser(id=user_id, email=email if isinstance(email, str) else None)


def _auth_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=1)
def get_token_verifier() -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier()


def require_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    verifier: SupabaseTokenVerifier = Depends(get_token_verifier),
) -> AuthenticatedUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _auth_error("authentication_required", "Sign in to continue.")
    return verifier.verify(token)
