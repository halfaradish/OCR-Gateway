from __future__ import annotations

import time
from io import BytesIO

import pytest


def _bench_image() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (2000, 1000), "white")
    font = ImageFont.load_default(size=64)
    draw = ImageDraw.Draw(image)
    for index in range(5):
        draw.text(
            (60, 150 + index * 140),
            f"OCR gateway benchmark line {index} 12345",
            fill="black",
            font=font,
        )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.slow
def test_local_ocr_p95_under_3s() -> None:
    pytest.importorskip("rapidocr")
    from app.workers import local_ocr

    image = _bench_image()
    assert local_ocr.warmup() is True

    samples: list[float] = []
    for _ in range(30):
        started = time.monotonic()
        payload = local_ocr.run_ocr(image, "zh")
        samples.append((time.monotonic() - started) * 1000)
        assert payload["text"]

    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    print(f"local OCR p95={p95:.1f}ms over {len(samples)} runs")
    assert p95 <= 3000
