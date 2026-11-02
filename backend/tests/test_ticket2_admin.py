from __future__ import annotations

from datetime import datetime

from conftest import ADMIN_PASSWORD, auth_headers, create_account, create_api_key, create_user

from app.models import Account, UsageEvent
from app.security import create_admin_token, verify_admin_token
from app.state import KeyRateLimiter


async def test_login_and_me(client) -> None:
    response = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["expires_in"] == 43200
    me = await client.get(
        "/api/admin/me", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert me.status_code == 200
    assert me.json() == {"username": "admin"}


async def test_admin_endpoints_require_token(client) -> None:
    response = await client.get("/api/admin/users")
    assert response.status_code == 401


async def test_login_rejects_wrong_password_and_rate_limits(client) -> None:
    for _ in range(5):
        response = await client.post("/api/admin/login", json={"password": "wrong-pass"})
        assert response.status_code == 401
    sixth = await client.post("/api/admin/login", json={"password": "wrong-pass"})
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "RATE_LIMITED"


def test_admin_token_expiry(settings) -> None:
    token = create_admin_token(settings.master_key_bytes)
    assert verify_admin_token(settings.master_key_bytes, token, 43200)
    assert not verify_admin_token(settings.master_key_bytes, token, -1)
    assert not verify_admin_token(settings.master_key_bytes, "not-a-token", 43200)


async def test_user_crud_and_duplicate_name(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "alice")
    duplicate = await client.post("/api/admin/users", json={"name": "alice"}, headers=admin_headers)
    assert duplicate.status_code == 400
    updated = await client.patch(
        f"/api/admin/users/{user['id']}", json={"enabled": False}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    deleted = await client.delete(f"/api/admin/users/{user['id']}", headers=admin_headers)
    assert deleted.status_code == 204


async def test_api_key_plaintext_only_once_and_defaults(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "bob")
    created = await create_api_key(client, admin_headers, user["id"], "bob-key")
    assert created["key"].startswith("ocr_")
    assert created["daily_limit"] == 100
    assert created["rpm_limit"] == 30
    listing = await client.get("/api/admin/api-keys", headers=admin_headers)
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    assert "key" not in rows[0]
    assert rows[0]["key_prefix"] == created["key"][:12]


async def test_api_key_explicit_null_limits(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "carol")
    created = await create_api_key(
        client, admin_headers, user["id"], "unlimited", daily_limit=None, rpm_limit=None
    )
    assert created["daily_limit"] is None
    assert created["rpm_limit"] is None


async def test_revoked_key_returns_401(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "dave")
    created = await create_api_key(client, admin_headers, user["id"], "dave-key")
    headers = auth_headers(created["key"])
    assert (await client.get("/v1/providers", headers=headers)).status_code == 200
    updated = await client.patch(
        f"/api/admin/api-keys/{created['id']}", json={"enabled": False}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert (await client.get("/v1/providers", headers=headers)).status_code == 401


async def test_disabled_user_invalidates_key(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "erin")
    created = await create_api_key(client, admin_headers, user["id"], "erin-key")
    headers = auth_headers(created["key"])
    await client.patch(
        f"/api/admin/users/{user['id']}", json={"enabled": False}, headers=admin_headers
    )
    assert (await client.get("/v1/providers", headers=headers)).status_code == 401


async def test_account_credentials_are_encrypted_and_masked(
    client, admin_headers, app
) -> None:
    account = await create_account(client, admin_headers, "baidu", "baidu-main")
    assert account["qps_limit"] == 5
    masked = account["credential_fields"]
    assert masked["secret_key"].endswith("****")
    assert "SK-test" not in str(masked)
    state = app.state.gw
    async with state.session_factory() as session:
        row = await session.get(Account, account["id"])
        assert row is not None
        assert "SK-test" not in row.credentials_enc
        assert "AK-test" not in row.credentials_enc


async def test_account_missing_secret_key_returns_400(client, admin_headers) -> None:
    response = await client.post(
        "/api/admin/accounts",
        json={
            "provider": "tencent",
            "name": "bad",
            "credentials": {"secret_id": "AKID"},
        },
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


async def test_quota_templates_and_no_auto_apply(client, admin_headers) -> None:
    templates = await client.get("/api/admin/quota-templates", headers=admin_headers)
    assert templates.status_code == 200
    body = templates.json()
    assert "以官网为准" in body["disclaimer"]
    codes = {item["code"] for item in body["providers"]}
    assert codes == {"baidu", "tencent"}
    account = await create_account(client, admin_headers, "baidu", "no-quota")
    assert account["quota_daily"] is None
    assert account["quota_monthly"] is None
    assert account["quota_total"] is None


async def test_api_key_auth_errors(client, admin_headers) -> None:
    assert (await client.get("/v1/providers")).status_code == 401
    assert (await client.get("/v1/providers", headers=auth_headers("ocr_bogus"))).status_code == 401


async def test_disabled_key_returns_401(client, admin_headers, app) -> None:
    user = await create_user(client, admin_headers, "frank")
    created = await create_api_key(client, admin_headers, user["id"], "frank-key")
    state = app.state.gw
    async with state.session_factory() as session:
        from app.models import ApiKey

        row = await session.get(ApiKey, created["id"])
        assert row is not None
        row.enabled = False
        await session.commit()
    assert (
        await client.get("/v1/providers", headers=auth_headers(created["key"]))
    ).status_code == 401


async def test_rpm_limit_returns_429(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "grace")
    created = await create_api_key(
        client, admin_headers, user["id"], "tight", rpm_limit=1, daily_limit=100
    )
    headers = auth_headers(created["key"])
    assert (await client.get("/v1/providers", headers=headers)).status_code == 200
    limited = await client.get("/v1/providers", headers=headers)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_rpm_bucket_recovers_after_window() -> None:
    limiter = KeyRateLimiter()
    assert limiter.allow(1, 1, now=0.0)
    assert not limiter.allow(1, 1, now=1.0)
    assert limiter.allow(1, 1, now=61.0)


async def test_daily_limit_returns_quota_exceeded(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "heidi")
    created = await create_api_key(
        client, admin_headers, user["id"], "zero", daily_limit=0, rpm_limit=30
    )
    response = await client.get("/v1/providers", headers=auth_headers(created["key"]))
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


async def test_admin_e2e_flow(client, admin_headers) -> None:
    user = await create_user(client, admin_headers, "ivan")
    created = await create_api_key(client, admin_headers, user["id"], "ivan-key")
    account = await create_account(client, admin_headers, "tencent", "tencent-main")
    accounts = await client.get("/api/admin/accounts", headers=admin_headers)
    assert accounts.status_code == 200
    payload = accounts.json()
    assert len(payload) == 1
    assert payload[0]["id"] == account["id"]
    assert "SK-test" not in str(payload)
    assert created["key"] not in str(payload)


async def test_usage_event_daily_limit_counts_quota_used(client, admin_headers, app) -> None:
    user = await create_user(client, admin_headers, "judy")
    created = await create_api_key(
        client, admin_headers, user["id"], "judy-key", daily_limit=1, rpm_limit=100
    )
    state = app.state.gw
    async with state.session_factory() as session:
        session.add(
            UsageEvent(
                request_id="seed-1",
                user_id=user["id"],
                api_key_id=created["id"],
                provider="baidu",
                success=True,
                latency_ms=10,
                quota_used=1,
                cached=False,
                created_at=datetime.utcnow(),
            )
        )
        await session.commit()
    response = await client.get("/v1/providers", headers=auth_headers(created["key"]))
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "QUOTA_EXCEEDED"


async def test_account_qps_explicit_null(client, admin_headers) -> None:
    account = await create_account(
        client, admin_headers, "baidu", "no-qps", qps_limit=None
    )
    assert account["qps_limit"] is None
