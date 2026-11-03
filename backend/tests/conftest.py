from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MASTER_KEY", base64.b64encode(b"t" * 32).decode("ascii")
)
os.environ.setdefault("ADMIN_PASSWORD", "password123")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="ocr-gateway-test-"))

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db import Base, make_engine  # noqa: E402
from app.main import create_app  # noqa: E402

TEST_MASTER_KEY = b"k" * 32
ADMIN_PASSWORD = "password123"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        master_key=base64.b64encode(TEST_MASTER_KEY).decode("ascii"),
        admin_password=ADMIN_PASSWORD,
        data_dir=str(tmp_path),
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        request_deadline_ms=20000,
        max_concurrent_requests=8,
        # Keep the panel out of unit tests even after a local build produced real assets;
        # panel tests point FRONTEND_DIST at their own temp directory.
        frontend_dist=str(tmp_path / "frontend-dist"),
    )


@pytest.fixture
async def app(settings: Settings):
    engine = make_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def app_factory():
    created = []

    async def factory(settings: Settings):
        engine = make_engine(settings.database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()
        application = create_app(settings)
        context = application.router.lifespan_context(application)
        await context.__aenter__()
        transport = httpx.ASGITransport(app=application)
        session = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        created.append((application, session, context))
        return application, session

    yield factory
    for _application, session, context in created:
        await session.aclose()
        await context.__aexit__(None, None, None)


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as session:
        yield session


@pytest.fixture
async def admin_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def create_user(client: httpx.AsyncClient, headers: dict[str, str], name: str) -> dict:
    response = await client.post("/api/admin/users", json={"name": name}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def create_api_key(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    user_id: int,
    name: str = "key",
    daily_limit: int | None = 100,
    rpm_limit: int | None = 30,
) -> dict:
    response = await client.post(
        "/api/admin/api-keys",
        json={
            "user_id": user_id,
            "name": name,
            "daily_limit": daily_limit,
            "rpm_limit": rpm_limit,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def create_account(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    provider: str = "baidu",
    name: str = "account",
    priority: int = 100,
    **overrides,
) -> dict:
    credentials = (
        {"app_id": "12345", "api_key": "AK-test", "secret_key": "SK-test"}
        if provider == "baidu"
        else {"secret_id": "AKID-test", "secret_key": "SK-test"}
    )
    body = {
        "provider": provider,
        "name": name,
        "priority": priority,
        "credentials": credentials,
    }
    body.update(overrides)
    response = await client.post("/api/admin/accounts", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def make_image_bytes(
    fmt: str = "PNG",
    size: tuple[int, int] = (120, 60),
    text: str = "hello",
    exif_orientation: int | None = None,
) -> bytes:
    from io import BytesIO

    from PIL import Image, ImageDraw

    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.text((8, 8), text, fill="black")
    buffer = BytesIO()
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[274] = exif_orientation
        image.save(buffer, format=fmt, exif=exif)
    else:
        image.save(buffer, format=fmt)
    return buffer.getvalue()
