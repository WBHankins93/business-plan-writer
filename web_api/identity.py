from __future__ import annotations

import os
import re

from fastapi import Header, HTTPException, Request, status


_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,35}$")


def authenticated_user_id(
    request: Request,
    x_authenticated_user_id: str | None = Header(
        default=None, alias="X-Authenticated-User-Id"
    ),
) -> str:
    """Adapt the existing authentication layer to owner-scoped billing calls.

    Production auth middleware should set ``request.state.authenticated_user_id``.
    The header adapter is only for a trusted proxy or local Stripe test-mode work;
    the proxy must remove user-supplied copies of this header.
    """

    user_id = getattr(request.state, "authenticated_user_id", None)
    if user_id is None and os.getenv("TRUST_AUTH_PROXY_HEADERS", "").lower() == "true":
        user_id = x_authenticated_user_id
    if not isinstance(user_id, str) or not _USER_ID_PATTERN.fullmatch(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "An authenticated user is required."},
        )
    return user_id
