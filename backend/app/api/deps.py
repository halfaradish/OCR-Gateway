from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quota import SHANGHAI
from app.models import ApiKey, UsageEvent, User
from app.security import hash_api_key, verify_admin_token
from app.state import AppState


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


async def require_admin(request: Request, state: AppState = Depends(get_state)) -> str:
    token = get_bearer_token(request)
    if token is None:
        raise ApiError(401, "UNAUTHORIZED", "missing admin token")
    if not verify_admin_token(
        state.settings.master_key_bytes, token, state.settings.session_ttl_seconds
    ):
        raise ApiError(401, "UNAUTHORIZED", "invalid admin token")
    return "admin"


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
