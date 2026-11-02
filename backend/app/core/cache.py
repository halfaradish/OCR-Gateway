from __future__ import annotations

import hashlib
import json
from typing import Any

from cachetools import TTLCache

MAX_RESULT_BYTES = 256 * 1024


class ResultCache:
    def __init__(self, enabled: bool, max_entries: int, ttl_seconds: int) -> None:
        self.enabled = enabled
        self._cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=max_entries, ttl=ttl_seconds
        )

    @staticmethod
    def build_key(image_bytes: bytes, language: str, provider: str) -> str:
        digest = hashlib.sha256(image_bytes).hexdigest()
        return f"{digest}:{language}:{provider}"

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return self._cache.get(key)

    def set(self, key: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        if not str(payload.get("text", "")):
            return
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(encoded) > MAX_RESULT_BYTES:
            return
        self._cache[key] = payload

    def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count

    def __len__(self) -> int:
        return len(self._cache)
