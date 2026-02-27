import json
import os
import time
from typing import Any

import jwt
import requests
from fastapi import Request
from fastapi.responses import JSONResponse
from jwt import InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware

JWKS_CACHE_TTL_SECONDS = 60 * 60

_jwks_cache: dict[str, Any] = {"keys": None, "expires_at": 0.0}


def _jwks_url() -> str:
  explicit = os.getenv("SUPABASE_JWKS_URL")
  if explicit:
    return explicit
  supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
  if not supabase_url:
    raise RuntimeError("SUPABASE_URL is not configured")
  return f"{supabase_url}/auth/v1/.well-known/jwks.json"


def _issuer() -> str:
  explicit = os.getenv("SUPABASE_ISSUER")
  if explicit:
    return explicit
  supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
  if not supabase_url:
    raise RuntimeError("SUPABASE_URL is not configured")
  return f"{supabase_url}/auth/v1"


def _audience() -> str:
  return os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")


def _fetch_jwks() -> list[dict[str, Any]]:
  now = time.time()
  if _jwks_cache["keys"] and _jwks_cache["expires_at"] > now:
    return _jwks_cache["keys"]

  response = requests.get(_jwks_url(), timeout=8)
  response.raise_for_status()
  payload = response.json()
  keys = payload.get("keys", [])
  if not isinstance(keys, list) or not keys:
    raise RuntimeError("Supabase JWKS payload is empty")

  _jwks_cache["keys"] = keys
  _jwks_cache["expires_at"] = now + JWKS_CACHE_TTL_SECONDS
  return keys


def verify_supabase_jwt(token: str) -> dict[str, Any]:
  unverified_header = jwt.get_unverified_header(token)
  kid = unverified_header.get("kid")
  if not kid:
    raise InvalidTokenError("Token header missing kid")

  jwk = next((k for k in _fetch_jwks() if k.get("kid") == kid), None)
  if not jwk:
    raise InvalidTokenError("Signing key not found")

  public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
  return jwt.decode(
    token,
    key=public_key,
    algorithms=["RS256"],
    audience=_audience(),
    issuer=_issuer(),
  )


def _extract_bearer_token(request: Request) -> str | None:
  header = request.headers.get("Authorization")
  if not header:
    return None
  scheme, _, token = header.partition(" ")
  if scheme.lower() != "bearer" or not token:
    raise InvalidTokenError("Invalid authorization header format")
  return token.strip()


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
  """
  Middleware validates Authorization Bearer tokens if present.
  It does not force auth globally; protected endpoints should use get_current_user.
  """

  async def dispatch(self, request: Request, call_next):
    request.state.user = None
    try:
      token = _extract_bearer_token(request)
      if token:
        request.state.user = verify_supabase_jwt(token)
    except (InvalidTokenError, RuntimeError, requests.RequestException) as exc:
      return JSONResponse(status_code=401, content={"detail": f"Unauthorized: {exc}"})

    return await call_next(request)
