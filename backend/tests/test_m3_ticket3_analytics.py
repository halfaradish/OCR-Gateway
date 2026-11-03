from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from conftest import auth_headers, create_account, create_api_key, create_user, make_image_bytes
from sqlalchemy import select

from app.db import utcnow
from app.models import QuotaCounter, UsageEvent

SHANGHAI = ZoneInfo("Asia/Shanghai")
TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"


def local_utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    moment = datetime(year, month, day, hour, minute, tzinfo=SHANGHAI)
    return moment.astimezone(UTC).replace(tzinfo=None)


def recent_window() -> dict[str, str]:
    """A <=90-day window (date form) that always contains `utcnow()`."""
    today = datetime.now(SHANGHAI).date()
    return {"from": (today - timedelta(days=1)).isoformat(), "to": today.isoformat()}


async def insert_events(app, *rows: dict) -> None:
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


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "tok", "expires_in": 2592000})


def words_response(*words: str) -> httpx.Response:
    return httpx.Response(200, json={"words_result": [{"words": word} for word in words]})


async def test_overview_without_requests_returns_nulls(client, admin_headers) -> None:
    response = await client.get("/api/admin/overview", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    today = body["today"]
    assert today["requests"] == 0
    assert today["success_rate"] is None
    assert today["cache_hit_rate"] is None
    assert today["avg_latency_ms"] is None
    assert today["auto_failures"] == 0
    assert len(body["series"]) == 7
    assert all(row["requests"] == 0 and row["avg_latency_ms"] is None for row in body["series"])
    assert [row["code"] for row in body["providers"]] == ["baidu", "tencent"]
    assert body["providers"][0]["available_accounts"] == 0
    assert body["accounts"] == []
    assert body["recent_errors"] == []
    assert body["cache"]["enabled"] is True
    assert body["generated_at"].endswith("+08:00")


async def test_overview_aggregates_today_and_recent_errors(client, admin_headers, app) -> None:
    user = await create_user(client, admin_headers, "member")
    account = await create_account(client, admin_headers, "tencent", "tencent-main")
    await insert_events(
        app,
        {"provider": "baidu", "cached": True, "latency_ms": 100, "user_id": user["id"]},
        {"provider": "baidu", "latency_ms": 300, "user_id": user["id"]},
        {
            "provider": "tencent",
            "success": False,
            "error_code": "TIMEOUT",
            "latency_ms": 500,
            "quota_used": 0,
            "account_id": account["id"],
        },
    )

    body = (await client.get("/api/admin/overview", headers=admin_headers)).json()
    today = body["today"]
    assert today["requests"] == 3
    assert today["success"] == 2
    assert today["failure"] == 1
    assert today["cached"] == 1
    assert today["quota_used"] == 2
    assert today["success_rate"] == round(2 / 3, 4)
    assert today["cache_hit_rate"] == round(1 / 3, 4)
    assert today["avg_latency_ms"] == 300

    error = body["recent_errors"][0]
    assert error["error_code"] == "TIMEOUT"
    assert error["account_name"] == "tencent-main"
    assert "text" not in error

    tencent = next(row for row in body["providers"] if row["code"] == "tencent")
    assert tencent["accounts"] == 1
    assert tencent["today_requests"] == 1
    assert tencent["today_failures"] == 1

    assert body["accounts"][0]["name"] == "tencent-main"
    assert "quota_usage" in body["accounts"][0]


async def test_overview_counts_auto_failures_separately(client, admin_headers, app) -> None:
    await insert_events(
        app,
        {"provider": "auto", "success": False, "error_code": "PROVIDER_UNAVAILABLE"},
        {"provider": "auto", "success": False, "error_code": "TIMEOUT"},
        {"provider": "auto", "success": True},  # routed successfully: not an auto failure
        {"provider": "baidu", "success": True},
    )
    body = (await client.get("/api/admin/overview", headers=admin_headers)).json()
    assert body["today"]["requests"] == 4
    assert body["today"]["auto_failures"] == 2
    baidu = next(row for row in body["providers"] if row["code"] == "baidu")
    assert baidu["today_requests"] == 1
    assert baidu["today_failures"] == 0


async def test_overview_available_accounts_is_read_only_snapshot(
    client, admin_headers, app
) -> None:
    first = await create_account(client, admin_headers, "baidu", "first")
    await create_account(client, admin_headers, "baidu", "second")
    await client.patch(
        f"/api/admin/accounts/{first['id']}", json={"enabled": False}, headers=admin_headers
    )

    state = app.state.gw
    states_before = {runtime.id: runtime.state for runtime in state.registry.all()}
    body = (await client.get("/api/admin/overview", headers=admin_headers)).json()
    states_after = {runtime.id: runtime.state for runtime in state.registry.all()}

    baidu = next(row for row in body["providers"] if row["code"] == "baidu")
    assert baidu["accounts"] == 2
    assert baidu["available_accounts"] == 1
    assert states_before == states_after


async def test_usage_series_buckets_by_shanghai_day(client, admin_headers, app) -> None:
    await insert_events(
        app,
        {"created_at": local_utc(2026, 11, 3, 23, 30)},
        {"created_at": local_utc(2026, 11, 4, 0, 30)},
        {"created_at": local_utc(2026, 11, 4, 23, 0)},
        {"created_at": local_utc(2026, 11, 5, 0, 0)},
    )
    response = await client.get(
        "/api/admin/usage/series",
        params={"from": "2026-11-03", "to": "2026-11-04"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["bucket"] == "day"
    assert body["from"] == "2026-11-03T00:00:00+08:00"
    # A date-only `to` covers the whole local day: exclusive next-midnight boundary.
    assert body["to"] == "2026-11-05T00:00:00+08:00"
    assert [row["date"] for row in body["rows"]] == ["2026-11-03", "2026-11-04"]
    assert [row["requests"] for row in body["rows"]] == [1, 2]


async def test_usage_series_defaults_to_seven_local_days(client, admin_headers) -> None:
    body = (await client.get("/api/admin/usage/series", headers=admin_headers)).json()
    assert len(body["rows"]) == 7
    today = datetime.now(SHANGHAI).date()
    assert body["rows"][-1]["date"] == today.isoformat()
    assert body["rows"][0]["date"] == (today - timedelta(days=6)).isoformat()


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/admin/usage/series", {"from": "2026-11-05", "to": "2026-11-04"}),
        ("/api/admin/usage/summary", {"from": "2026-11-05", "to": "2026-11-04"}),
        ("/api/admin/logs", {"from": "2026-11-05", "to": "2026-11-04"}),
        ("/api/admin/usage/series", {"from": "2025-01-01", "to": "2026-11-04"}),
        ("/api/admin/usage/summary", {"from": "2025-01-01", "to": "2026-11-04"}),
        ("/api/admin/logs", {"from": "2025-01-01", "to": "2026-11-04"}),
        ("/api/admin/usage/series", {"from": "not-a-time"}),
        ("/api/admin/usage/summary", {"from": "2026-13-40"}),
        ("/api/admin/logs", {"to": "yesterday"}),
    ],
)
async def test_time_window_validation(client, admin_headers, path, params) -> None:
    response = await client.get(path, params=params, headers=admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


async def test_usage_series_filters(client, admin_headers, app) -> None:
    first = await create_user(client, admin_headers, "first-user")
    second = await create_user(client, admin_headers, "second-user")
    account_a = await create_account(client, admin_headers, "baidu", "account-a")
    account_b = await create_account(client, admin_headers, "tencent", "account-b")
    await insert_events(
        app,
        {"user_id": first["id"], "account_id": account_a["id"], "provider": "baidu"},
        {"user_id": first["id"], "account_id": account_a["id"], "provider": "baidu"},
        {"user_id": second["id"], "account_id": account_b["id"], "provider": "tencent"},
    )
    window = recent_window()

    by_user = (
        await client.get(
            "/api/admin/usage/series",
            params={**window, "user_id": first["id"]},
            headers=admin_headers,
        )
    ).json()
    assert sum(row["requests"] for row in by_user["rows"]) == 2

    by_provider = (
        await client.get(
            "/api/admin/usage/series",
            params={**window, "provider": "tencent"},
            headers=admin_headers,
        )
    ).json()
    assert sum(row["requests"] for row in by_provider["rows"]) == 1

    by_account = (
        await client.get(
            "/api/admin/usage/series",
            params={**window, "account_id": account_b["id"]},
            headers=admin_headers,
        )
    ).json()
    assert sum(row["requests"] for row in by_account["rows"]) == 1


async def test_usage_summary_labels_latency_and_null_last(client, admin_headers, app) -> None:
    first = await create_user(client, admin_headers, "alice")
    second = await create_user(client, admin_headers, "bob")
    account = await create_account(client, admin_headers, "baidu", "baidu-main")
    await insert_events(
        app,
        {"user_id": first["id"], "latency_ms": 100},
        {"user_id": first["id"], "latency_ms": 200},
        {"user_id": second["id"], "latency_ms": 300},
        {"user_id": None, "latency_ms": 400},  # deleted member -> SET NULL
        {"provider": "auto", "account_id": account["id"]},
    )
    window = recent_window()

    by_user = (
        await client.get(
            "/api/admin/usage/summary",
            params={**window, "group_by": "user"},
            headers=admin_headers,
        )
    ).json()
    keys = [row["key"] for row in by_user["rows"]]
    assert keys == [first["id"], second["id"], None]
    labels = {row["key"]: row["label"] for row in by_user["rows"]}
    assert labels[first["id"]] == "alice"
    assert labels[second["id"]] == "bob"
    assert labels[None] is None
    alice = next(row for row in by_user["rows"] if row["key"] == first["id"])
    assert alice["requests"] == 2
    assert alice["avg_latency_ms"] == 150
    assert by_user["rows"][-1]["key"] is None
    assert by_user["rows"][-1]["requests"] == 2  # both null-owner events

    by_provider = (
        await client.get(
            "/api/admin/usage/summary",
            params={**window, "group_by": "provider"},
            headers=admin_headers,
        )
    ).json()
    provider_labels = {row["key"]: row["label"] for row in by_provider["rows"]}
    assert provider_labels["auto"] == "自动路由"
    assert provider_labels["baidu"] == "百度智能云"

    by_account = (
        await client.get(
            "/api/admin/usage/summary",
            params={**window, "group_by": "account"},
            headers=admin_headers,
        )
    ).json()
    assert by_account["rows"][-1]["key"] is None
    assert by_account["rows"][-1]["label"] is None

    filtered = (
        await client.get(
            "/api/admin/usage/summary",
            params={**window, "group_by": "user", "user_id": second["id"]},
            headers=admin_headers,
        )
    ).json()
    assert [row["key"] for row in filtered["rows"]] == [second["id"]]


async def test_logs_filters_pagination_and_names(client, admin_headers, app) -> None:
    user = await create_user(client, admin_headers, "member")
    account = await create_account(client, admin_headers, "baidu", "baidu-main")
    await insert_events(
        app,
        {"user_id": user["id"], "account_id": account["id"], "success": True},
        {
            "user_id": user["id"],
            "account_id": account["id"],
            "success": False,
            "error_code": "TIMEOUT",
        },
        {"user_id": None, "account_id": None, "success": True},  # deleted entities
    )
    window = recent_window()

    all_rows = (
        await client.get("/api/admin/logs", params=window, headers=admin_headers)
    ).json()
    assert all_rows["total"] == 3
    ids = [row["id"] for row in all_rows["rows"]]
    assert ids == sorted(ids, reverse=True)
    assert {row["user_name"] for row in all_rows["rows"]} == {"member", None}
    assert {row["account_name"] for row in all_rows["rows"]} == {"baidu-main", None}

    failed = (
        await client.get(
            "/api/admin/logs", params={**window, "success": "false"}, headers=admin_headers
        )
    ).json()
    assert failed["total"] == 1
    assert failed["rows"][0]["error_code"] == "TIMEOUT"

    by_error = (
        await client.get(
            "/api/admin/logs",
            params={**window, "error_code": "TIMEOUT"},
            headers=admin_headers,
        )
    ).json()
    assert by_error["total"] == 1

    by_provider = (
        await client.get(
            "/api/admin/logs",
            params={**window, "provider": "tencent"},
            headers=admin_headers,
        )
    ).json()
    assert by_provider["total"] == 0
    assert by_provider["rows"] == []

    page = (
        await client.get(
            "/api/admin/logs", params={**window, "limit": 2, "offset": 0}, headers=admin_headers
        )
    ).json()
    assert page["total"] == 3
    assert len(page["rows"]) == 2

    assert "text" not in page["rows"][0]


async def test_logs_date_form_to_includes_whole_day(client, admin_headers, app) -> None:
    await insert_events(
        app,
        {"created_at": local_utc(2026, 11, 4, 23, 59)},
        {"created_at": local_utc(2026, 11, 5, 0, 0)},
    )
    body = (
        await client.get(
            "/api/admin/logs",
            params={"from": "2026-11-04", "to": "2026-11-04"},
            headers=admin_headers,
        )
    ).json()
    assert body["total"] == 1


async def test_accounts_quota_usage_and_owner_name(
    client, admin_headers, app
) -> None:
    user = await create_user(client, admin_headers, "小明")
    key = await create_api_key(
        client, admin_headers, user["id"], "member-key", daily_limit=100, rpm_limit=100
    )
    account = await create_account(
        client,
        admin_headers,
        "baidu",
        "baidu-main",
        owner_id=user["id"],
        quota_daily=100,
        quota_monthly=1000,
    )
    assert account["owner_name"] == "小明"
    assert account["quota_usage"]["daily"]["used"] == 0

    with respx.mock(assert_all_called=False) as mock:
        mock.post(TOKEN_URL).mock(return_value=token_response())
        mock.post(OCR_URL).mock(return_value=words_response("hello"))
        response = await client.post(
            "/v1/ocr/image",
            headers=auth_headers(key["key"]),
            files={"file": ("a.png", make_image_bytes(text="quota"), "image/png")},
        )
    assert response.status_code == 200, response.text

    listed = (await client.get("/api/admin/accounts", headers=admin_headers)).json()
    row = next(item for item in listed if item["id"] == account["id"])
    usage = row["quota_usage"]
    assert usage["daily"]["used"] == 1
    assert usage["daily"]["limit"] == 100
    assert usage["monthly"]["used"] == 1
    assert usage["monthly"]["limit"] == 1000
    assert usage["total"]["used"] == 1
    assert usage["total"]["limit"] is None
    assert usage["total"]["period_key"] == "all"
    assert row["owner_name"] == "小明"

    await client.delete(f"/api/admin/users/{user['id']}", headers=admin_headers)
    after = (await client.get("/api/admin/accounts", headers=admin_headers)).json()
    assert next(item for item in after if item["id"] == account["id"])["owner_name"] is None


async def test_account_quota_daily_resets_after_period_change(
    client, admin_headers, app
) -> None:
    account = await create_account(
        client, admin_headers, "baidu", "baidu-daily", quota_daily=10
    )
    state = app.state.gw
    runtime = state.registry.get(account["id"])
    assert runtime is not None
    state.quota.increment(runtime)

    before = (await client.get("/api/admin/accounts", headers=admin_headers)).json()
    assert next(item for item in before if item["id"] == account["id"])["quota_usage"]["daily"]["used"] == 1

    tomorrow = utcnow() + timedelta(days=1)
    assert state.quota.used(runtime, "daily", tomorrow) == 0
    state.quota.increment(runtime, tomorrow)
    later = (await client.get("/api/admin/accounts", headers=admin_headers)).json()
    assert next(item for item in later if item["id"] == account["id"])["quota_usage"]["daily"]["used"] == 1


async def test_delete_account_clears_quota_counters(client, admin_headers, app) -> None:
    account = await create_account(client, admin_headers, "baidu", "to-delete")
    state = app.state.gw
    runtime = state.registry.get(account["id"])
    assert runtime is not None
    state.quota.increment(runtime)

    response = await client.delete(
        f"/api/admin/accounts/{account['id']}", headers=admin_headers
    )
    assert response.status_code == 204

    async with state.session_factory() as session:
        await state.quota.flush(session)
    async with state.session_factory() as session:
        await state.quota.flush(session)
    async with state.session_factory() as session:
        counters = (await session.execute(select(QuotaCounter))).scalars().all()
    assert [counter.account_id for counter in counters] == []
