from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db import utcnow
from app.models import UsageEvent

SHANGHAI = ZoneInfo("Asia/Shanghai")


def recent_window() -> dict[str, str]:
    today = datetime.now(SHANGHAI).date()
    return {"from": (today - timedelta(days=1)).isoformat(), "to": today.isoformat()}


async def _insert_events(app, *rows: dict) -> None:
    state = app.state.gw
    async with state.session_factory() as session:
        for row in rows:
            payload = {
                "request_id": f"req-{uuid.uuid4()}",
                "user_id": None,
                "api_key_id": None,
                "account_id": None,
                "provider": "baidu",
                "capability": "general_text",
                "success": True,
                "error_code": None,
                "latency_ms": 100,
                "quota_used": 1,
                "cached": False,
                "image_hash": None,
                "created_at": utcnow(),
            }
            payload.update(row)
            session.add(UsageEvent(**payload))
        await session.commit()


async def test_local_provider_label_in_summary_and_logs(
    app, client, admin_headers
) -> None:
    await _insert_events(
        app,
        {"provider": "local", "quota_used": 0, "latency_ms": 40},
        {"provider": "baidu", "quota_used": 1, "latency_ms": 100},
    )
    window = recent_window()

    summary = (
        await client.get(
            "/api/admin/usage/summary",
            params={**window, "group_by": "provider"},
            headers=admin_headers,
        )
    ).json()
    labels = {row["key"]: row["label"] for row in summary["rows"]}
    assert labels["local"] == "本地 RapidOCR"
    assert labels["baidu"] == "百度智能云"

    filtered = (
        await client.get(
            "/api/admin/usage/summary",
            params={**window, "group_by": "provider", "provider": "local"},
            headers=admin_headers,
        )
    ).json()
    assert [row["key"] for row in filtered["rows"]] == ["local"]
    assert filtered["rows"][0]["requests"] == 1

    logs = (
        await client.get(
            "/api/admin/logs",
            params={**window, "provider": "local"},
            headers=admin_headers,
        )
    ).json()
    assert logs["total"] == 1
    assert logs["rows"][0]["provider"] == "local"


async def test_overview_includes_local_row_and_reconciles(
    app, client, admin_headers
) -> None:
    await _insert_events(
        app,
        {"provider": "local", "quota_used": 0},
        {"provider": "baidu", "quota_used": 1},
    )
    window = recent_window()

    overview = (
        await client.get("/api/admin/overview", headers=admin_headers)
    ).json()
    providers = {row["code"]: row for row in overview["providers"]}
    assert providers["local"]["name"] == "本地 RapidOCR"
    assert providers["local"]["accounts"] == 0
    assert providers["local"]["available_accounts"] == 0
    assert providers["local"]["today_requests"] == 1
    assert sum(row["today_requests"] for row in overview["providers"]) == overview["today"]["requests"]

    series = (
        await client.get(
            "/api/admin/usage/series",
            params={**window, "provider": "local"},
            headers=admin_headers,
        )
    ).json()
    assert sum(bucket["requests"] for bucket in series["rows"]) == 1


async def test_overview_omits_local_row_without_events(
    app, client, admin_headers
) -> None:
    overview = (
        await client.get("/api/admin/overview", headers=admin_headers)
    ).json()
    codes = [row["code"] for row in overview["providers"]]
    assert "local" not in codes
