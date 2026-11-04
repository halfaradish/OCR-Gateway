#!/usr/bin/env python3
"""Image smoke for the local OCR path.

Starts a 0.3.0 container with a throwaway data volume, enables local OCR through the
admin API, waits for ``ready``, and verifies:

* explicit ``provider=local`` returns 200 with ``quota.used=0``;
* ``provider=auto`` falls back to local when no cloud account exists;
* disabling the switch makes explicit ``local`` return 403.

Run with the backend virtualenv (needs httpx + Pillow)::

    backend/.venv/Scripts/python.exe scripts/smoke_local_ocr.py --port 18080

The script never touches the host data directory and always removes the container.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import uuid
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

ADMIN_PASSWORD = "smoke-password-123"
MASTER_KEY = "k" * 32


def _image() -> bytes:
    image = Image.new("RGB", (520, 120), "white")
    font = ImageFont.load_default(size=36)
    ImageDraw.Draw(image).text((20, 40), "OCR gateway smoke 12345", fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _run(args: list[str]) -> str:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def _wait_health(client: httpx.Client, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = client.get("/healthz")
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1.0)
    raise RuntimeError("container did not become healthy")


def _admin_token(client: httpx.Client) -> dict[str, str]:
    response = client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _wait_ready(client: httpx.Client, headers: dict[str, str], timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get("/api/admin/local-ocr/status", headers=headers).json()
        if status["state"] == "ready":
            return status
        if status["state"] in ("error", "unavailable"):
            raise RuntimeError(f"local OCR failed to become ready: {json.dumps(status)}")
        time.sleep(1.0)
    raise RuntimeError("local OCR did not become ready in time")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="ocr-gateway:0.3.0")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--keep", action="store_true", help="keep the container for debugging")
    args = parser.parse_args()

    container = f"ocr-gateway-smoke-{uuid.uuid4().hex[:8]}"
    tmp = Path(tempfile.mkdtemp(prefix="ocr-gateway-smoke-"))
    base = f"http://127.0.0.1:{args.port}"
    try:
        _run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                container,
                "-p",
                f"127.0.0.1:{args.port}:8000",
                "-e",
                f"MASTER_KEY={MASTER_KEY}",
                "-e",
                f"ADMIN_PASSWORD={ADMIN_PASSWORD}",
                "-e",
                "LOCAL_OCR_ENABLED=false",
                "-v",
                f"{tmp}:/data",
                args.image,
            ]
        )
        with httpx.Client(base_url=base, timeout=120.0) as client:
            _wait_health(client)
            headers = _admin_token(client)

            user = client.post("/api/admin/users", json={"name": "smoke"}, headers=headers)
            user.raise_for_status()
            key = client.post(
                "/api/admin/api-keys",
                json={"user_id": user.json()["id"], "name": "smoke", "daily_limit": 100, "rpm_limit": 60},
                headers=headers,
            )
            key.raise_for_status()
            auth = {"Authorization": f"Bearer {key.json()['key']}"}

            enabled = client.put(
                "/api/admin/settings",
                json={"local_ocr_enabled": True},
                headers=headers,
            )
            enabled.raise_for_status()
            status = _wait_ready(client, headers)
            print(f"local OCR ready: {json.dumps(status, ensure_ascii=False)}")

            explicit = client.post(
                "/v1/ocr/image",
                headers=auth,
                data={"provider": "local"},
                files={"file": ("smoke.png", _image(), "image/png")},
            )
            explicit.raise_for_status()
            body = explicit.json()
            if body["provider"] != "local" or body["quota"]["used"] != 0:
                raise RuntimeError(f"unexpected local response: {body}")
            print(f"explicit local: {body['provider']} quota.used={body['quota']['used']}")

            fallback = client.post(
                "/v1/ocr/image",
                headers=auth,
                files={"file": ("smoke2.png", _image(), "image/png")},
            )
            fallback.raise_for_status()
            if fallback.json()["provider"] != "local":
                raise RuntimeError(f"auto did not fall back: {fallback.json()}")
            print("auto fallback: local")

            disabled = client.put(
                "/api/admin/settings",
                json={"local_ocr_enabled": False},
                headers=headers,
            )
            disabled.raise_for_status()
            forbidden = client.post(
                "/v1/ocr/image",
                headers=auth,
                data={"provider": "local"},
                files={"file": ("smoke3.png", _image(), "image/png")},
            )
            if forbidden.status_code != 403:
                raise RuntimeError(
                    f"expected 403 after disable, got {forbidden.status_code}: {forbidden.text}"
                )
            print("disabled local: 403")
    except Exception:
        try:
            logs = _run(["docker", "logs", "--tail", "80", container])
            print(logs, file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - best-effort diagnostics
            print(f"[smoke] docker logs unavailable: {exc}", file=sys.stderr)
        raise
    finally:
        if not args.keep:
            subprocess.run(
                ["docker", "rm", "-f", container], check=False, capture_output=True
            )
    print("image smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
