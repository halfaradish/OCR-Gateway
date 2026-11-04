"""Local OCR worker (runs inside the spawn process pool).

The module is intentionally self-contained: it must not import ``app.state`` /
``app.main`` / ``app.config`` so a spawn child never pulls application secrets or
database handles into its address space.  The engine is created lazily on first
use (and cached for the process lifetime).
"""

from __future__ import annotations

import os
import threading
from io import BytesIO
from typing import Any

_engine: Any | None = None
_lock = threading.Lock()

SENSITIVE_ENV = ("MASTER_KEY", "ADMIN_PASSWORD")


def worker_init() -> None:
    """Drop credentials inherited through ``os.environ`` before the first task."""
    for name in SENSITIVE_ENV:
        os.environ.pop(name, None)


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from rapidocr import RapidOCR

                _engine = RapidOCR()
    return _engine


def _warmup_image() -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (360, 80), "white")
    ImageDraw.Draw(image).text((10, 30), "OCR gateway warmup 12345", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def warmup() -> bool:
    """Load every model by running a text-bearing image through the full pipeline."""
    result = _get_engine()(_warmup_image())
    texts = getattr(result, "txts", None) or ()
    return any(str(text).strip() for text in texts)


def run_ocr(image_bytes: bytes, language: str) -> dict[str, Any]:
    """Recognize one image and normalize the engine output.

    ``language`` is accepted for API symmetry; the bundled models serve
    ``zh``/``en``/``auto`` identically.
    """
    del language
    result = _get_engine()(image_bytes)
    texts = tuple(getattr(result, "txts", None) or ())
    scores = tuple(getattr(result, "scores", None) or ())
    lines: list[dict[str, Any]] = []
    for index, text in enumerate(texts):
        score = scores[index] if index < len(scores) else None
        lines.append(
            {
                "text": str(text),
                "confidence": None if score is None else float(score),
            }
        )
    text = "\n".join(str(item) for item in texts)
    return {
        "text": text,
        "lines": lines,
        "warnings": [] if text else ["EMPTY_TEXT"],
    }
