from __future__ import annotations

import time
from datetime import timedelta

import pytest
from conftest import ADMIN_PASSWORD
from sqlalchemy import insert

from app.db import utcnow
from app.models import UsageEvent

BENCH_EVENTS = 100_000
CHUNK = 10_000
P95_BUDGET_MS = 300.0


def _rows() -> list[dict]:
    now = utcnow()
    providers = ("baidu", "tencent", "auto")
    rows = []
    for index in range(BENCH_EVENTS):
        success = index % 10 != 0
        rows.append(
            {
                "request_id": f"bench-{index}",
                "user_id": None,
                "api_key_id": None,
                "account_id": None,
                "provider": providers[index % 3],
                "capability": "general_text",
                "success": success,
                "error_code": None if success else "TIMEOUT",
                "latency_ms": 50 + (index % 1950),
                "quota_used": 0 if index % 5 == 0 else 1,
                "cached": index % 7 == 0,
                "image_hash": None,
                "created_at": now - timedelta(minutes=index % (60 * 24 * 60)),
            }
        )
    return rows


async def _seed(app) -> None:
    state = app.state.gw
    rows = _rows()
    async with state.session_factory() as session:
        for start in range(0, len(rows), CHUNK):
            await session.execute(insert(UsageEvent), rows[start : start + CHUNK])
        await session.commit()


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(round(0.95 * len(ordered))) - 1))
    return ordered[index]


def _report(name: str, samples: list[float]) -> None:
    p50 = sorted(samples)[len(samples) // 2]
    print(
        f"bench {name}: p50={p50:.1f}ms p95={_p95(samples):.1f}ms "
        f"max={max(samples):.1f}ms n={len(samples)}"
    )


@pytest.mark.slow
async def test_analytics_query_latency_under_300ms(app, client) -> None:
    await _seed(app)
    login = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    window = {"from": (today - timedelta(days=6)).isoformat(), "to": today.isoformat()}

    endpoints = {
        "series": ("/api/admin/usage/series", window),
        "summary": ("/api/admin/usage/summary", {**window, "group_by": "provider"}),
        "logs": ("/api/admin/logs", {**window, "limit": 50}),
    }

    for name, (path, params) in endpoints.items():
        samples: list[float] = []
        for _ in range(5):
            started = time.monotonic()
            response = await client.get(path, params=params, headers=headers)
            samples.append((time.monotonic() - started) * 1000)
            assert response.status_code == 200, response.text
        _report(name, samples)
        assert _p95(samples) < P95_BUDGET_MS, (name, samples)
