import os
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException, Request, status

from app.auth import verify_supabase_jwt

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_DEFAULT = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))

_request_windows: dict[str, deque[float]] = defaultdict(deque)


def _extract_user_from_request(request: Request) -> dict[str, Any]:
    if getattr(request.state, "user", None):
        return request.state.user

    header = request.headers.get("Authorization")
    if not header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    try:
        return verify_supabase_jwt(token.strip())
    except Exception as exc:  # noqa: BLE001 - convert all verification errors to 401
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {exc}") from exc


def _rate_limit(user_key: str) -> None:
    now = time.time()
    bucket = _request_windows[user_key]

    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_DEFAULT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry after 1 minute.",
        )

    bucket.append(now)


def get_current_user(request: Request) -> dict[str, Any]:
    payload = _extract_user_from_request(request)
    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing user id")

    # Placeholder limiter (in-memory). Replace with Redis in multi-instance deployments.
    _rate_limit(user_id)

    return {
        "user_id": user_id,
        "email": email,
    }
