from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def decode_master_key(value: str) -> bytes:
    """Accept hex or base64 encoded 32-byte key; also accept a literal 32-byte string."""
    raw = value.strip()
    if not raw:
        raise ValueError("MASTER_KEY 为空")
    try:
        decoded = bytes.fromhex(raw)
    except ValueError:
        decoded = b""
    if len(decoded) == 32:
        return decoded
    for decoder in ("standard", "urlsafe"):
        try:
            if decoder == "standard":
                decoded = base64.b64decode(raw, validate=True)
            else:
                decoded = base64.urlsafe_b64decode(raw)
        except Exception:  # noqa: BLE001 - try the next encoding
            continue
        if len(decoded) == 32:
            return decoded
    if len(raw.encode("utf-8")) == 32:
        return raw.encode("utf-8")
    raise ValueError("MASTER_KEY 必须是 32 字节（hex、base64 或 32 字符原文）")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    master_key: str = Field(..., description="32-byte key, hex/base64/literal")
    admin_password: str = Field(..., description="admin password, >= 8 chars")
    data_dir: str = "./data"
    database_url: str = ""
    default_timeout_ms: int = 8000
    request_deadline_ms: int = 20000
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_entries: int = 1000
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    max_concurrent_requests: int = 8
    url_fetch_timeout_seconds: float = 10.0
    url_fetch_max_bytes: int = 10 * 1024 * 1024
    session_ttl_seconds: int = 43200
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        self.master_key_bytes  # noqa: B018 - trigger decode validation
        if len(self.admin_password) < 8:
            raise ValueError("ADMIN_PASSWORD 必须至少 8 个字符")
        if not self.database_url:
            db_path = Path(self.data_dir) / "ocr-gateway.db"
            self.database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        return self

    @property
    def master_key_bytes(self) -> bytes:
        return decode_master_key(self.master_key)

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    def test_overrides(self, **kwargs: Any) -> Settings:
        data = self.model_dump()
        data.update(kwargs)
        return Settings(**data)


def enforce_single_worker() -> None:
    """Refuse to start when more than one worker is requested (design D17)."""
    values: list[tuple[str, str]] = []
    for name in ("WEB_CONCURRENCY", "UVICORN_WORKERS"):
        raw = os.environ.get(name)
        if raw:
            values.append((name, raw))
    argv = sys.argv
    for idx, token in enumerate(argv):
        if token == "--workers" and idx + 1 < len(argv):
            values.append(("--workers", argv[idx + 1]))
        elif token.startswith("--workers="):
            values.append(("--workers", token.split("=", 1)[1]))
    for name, raw in values:
        try:
            workers = int(raw)
        except ValueError:
            continue
        if workers > 1:
            raise RuntimeError(
                f"单实例约束：检测到 {name}={workers}，本服务只允许单 worker；"
                "请去掉 --workers 或设为 1"
            )
