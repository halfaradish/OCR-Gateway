from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quota import SHANGHAI
from app.models import ApiKey, UsageEvent, User
from app.security import constant_time_equals, hash_api_key, verify_admin_token
from app.state import AppState

ADMIN_SESSION_COOKIE = "ocr_admin_session"
ADMIN_CSRF_COOKIE = "ocr_csrf"
ADMIN_CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Declared (auto_error=False) so /docs renders an Authorize button; the token itself is read
# from the raw header below, which lets us reject a bad Bearer instead of silently falling back
# to the session cookie.
bearer_scheme = HTTPBearer(auto_error=False, description="Admin bearer token")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class KeyContext:
    key: ApiKey
    user: User


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.gw
    return state


async def get_session(state: AppState = Depends(get_state)) -> AsyncIterator[AsyncSession]:
    async with state.session_factory() as session:
        yield session


def get_bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def require_admin(
    request: Request,
    state: AppState = Depends(get_state),
    _credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Accept a Bearer token or the admin session cookie, with CSRF for cookie writes.

    A present-but-invalid `Authorization` header is a hard 401: falling back to a cookie would
    let a stale header silently drive the browser session. Bearer callers never need CSRF.
    """
    if request.headers.get("Authorization") is not None:
        token = get_bearer_token(request)
        if token is None or not verify_admin_token(
            state.settings.master_key_bytes, token, state.settings.session_ttl_seconds
        ):
            raise ApiError(401, "UNAUTHORIZED", "invalid admin token")
        request.state.admin_auth_source = "bearer"
        return "admin"

    cookie = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not cookie:
        raise ApiError(401, "UNAUTHORIZED", "missing admin token")
    if not verify_admin_token(
        state.settings.master_key_bytes, cookie, state.settings.session_ttl_seconds
    ):
        raise ApiError(401, "UNAUTHORIZED", "invalid admin token")

    if request.method.upper() not in SAFE_METHODS:
        supplied = request.headers.get(ADMIN_CSRF_HEADER, "")
        expected = request.cookies.get(ADMIN_CSRF_COOKIE, "")
        if not supplied or not expected or not constant_time_equals(supplied, expected):
            raise ApiError(403, "FORBIDDEN", "csrf token missing or invalid")

    request.state.admin_auth_source = "cookie"
    return "admin"


def request_is_https(request: Request, state: AppState) -> bool:
    """Decide the cookie `Secure` flag (direct TLS or a trusted reverse proxy)."""
    if request.url.scheme == "https":
        return True
    if state.settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-proto", "")
        first = forwarded.split(",")[0].strip().lower()
        if first == "https":
            return True
    return False


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_admin_cookies(
    response: Response, request: Request, state: AppState, token: str, csrf_token: str
) -> None:
    ttl = state.settings.session_ttl_seconds
    secure = request_is_https(request, state)
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        max_age=ttl,
        path="/",
        samesite="lax",
        secure=secure,
        httponly=True,
    )
    # Readable by the SPA so it can echo the value in X-CSRF-Token (double submit).
    response.set_cookie(
        ADMIN_CSRF_COOKIE,
        csrf_token,
        max_age=ttl,
        path="/",
        samesite="lax",
        secure=secure,
        httponly=False,
    )


def set_csrf_cookie(
    response: Response, request: Request, state: AppState, csrf_token: str
) -> None:
    """Refresh only the CSRF cookie (used by GET /me; the session cookie stays untouched)."""
    response.set_cookie(
        ADMIN_CSRF_COOKIE,
        csrf_token,
        max_age=state.settings.session_ttl_seconds,
        path="/",
        samesite="lax",
        secure=request_is_https(request, state),
        httponly=False,
    )


def clear_admin_cookies(response: Response, request: Request, state: AppState) -> None:
    secure = request_is_https(request, state)
    for name in (ADMIN_SESSION_COOKIE, ADMIN_CSRF_COOKIE):
        response.delete_cookie(name, path="/", samesite="lax", secure=secure)


def utc_start_of_today() -> datetime:
    local = datetime.now(SHANGHAI)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC).replace(tzinfo=None)


async def require_api_key(
    request: Request,
    state: AppState = Depends(get_state),
    session: AsyncSession = Depends(get_session),
) -> KeyContext:
    token = get_bearer_token(request)
    if token is None:
        raise ApiError(401, "UNAUTHORIZED", "missing api key")
    key_hash = hash_api_key(token)
    row = (
        await session.execute(
            select(ApiKey, User)
            .join(User, ApiKey.user_id == User.id)
            .where(ApiKey.key_hash == key_hash)
        )
    ).first()
    if row is None:
        raise ApiError(401, "UNAUTHORIZED", "invalid api key")
    key, user = row
    if not key.enabled or not user.enabled:
        raise ApiError(401, "UNAUTHORIZED", "api key disabled")
    if not state.key_limiter.allow(key.id, key.rpm_limit):
        raise ApiError(429, "RATE_LIMITED", "request rate limit exceeded")
    if key.daily_limit is not None:
        used = (
            await session.execute(
                select(func.coalesce(func.sum(UsageEvent.quota_used), 0)).where(
                    UsageEvent.api_key_id == key.id,
                    UsageEvent.created_at >= utc_start_of_today(),
                )
            )
        ).scalar_one()
        if int(used) >= key.daily_limit:
            raise ApiError(429, "QUOTA_EXCEEDED", "daily quota exhausted")
    return KeyContext(key=key, user=user)
