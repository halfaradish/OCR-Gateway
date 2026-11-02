from __future__ import annotations

from io import BytesIO

import pytest
from conftest import make_image_bytes
from PIL import Image

from app.providers.base import ImageError
from app.utils.images import image_hash, normalize_image

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000


def test_rejects_non_image_bytes() -> None:
    with pytest.raises(ImageError):
        normalize_image(b"definitely not an image", "baidu", MAX_BYTES, MAX_PIXELS)


def test_rejects_unsupported_format() -> None:
    gif = make_image_bytes("GIF")
    with pytest.raises(ImageError):
        normalize_image(gif, "baidu", MAX_BYTES, MAX_PIXELS)


def test_rejects_oversized_payload() -> None:
    with pytest.raises(ImageError):
        normalize_image(b"x" * 101, "baidu", 100, MAX_PIXELS)


def test_rejects_pixel_bomb_before_decode() -> None:
    small = make_image_bytes(size=(20, 20))
    with pytest.raises(ImageError):
        normalize_image(small, "baidu", MAX_BYTES, 100)


def test_rejects_too_small_image() -> None:
    tiny = make_image_bytes(size=(10, 10))
    with pytest.raises(ImageError):
        normalize_image(tiny, "baidu", MAX_BYTES, MAX_PIXELS)


def test_accepts_bmp_and_emits_jpeg() -> None:
    encoded = normalize_image(make_image_bytes("BMP"), "baidu", MAX_BYTES, MAX_PIXELS)
    assert encoded.startswith(b"\xff\xd8\xff")
    with Image.open(BytesIO(encoded)) as image:
        assert image.format == "JPEG"


def test_applies_exif_rotation() -> None:
    source = make_image_bytes("JPEG", size=(120, 60), exif_orientation=6)
    encoded = normalize_image(source, "baidu", MAX_BYTES, MAX_PIXELS)
    with Image.open(BytesIO(encoded)) as image:
        assert image.size == (60, 120)


def test_downscales_to_baidu_max_side() -> None:
    source = make_image_bytes("JPEG", size=(5000, 120))
    encoded = normalize_image(source, "baidu", MAX_BYTES, MAX_PIXELS)
    with Image.open(BytesIO(encoded)) as image:
        assert max(image.size) <= 4096
        assert min(image.size) >= 15


def test_tencent_allows_wider_image() -> None:
    source = make_image_bytes("JPEG", size=(5000, 120))
    encoded = normalize_image(source, "tencent", MAX_BYTES, MAX_PIXELS)
    with Image.open(BytesIO(encoded)) as image:
        assert image.width == 5000


def test_image_hash_is_16_hex_chars() -> None:
    digest = image_hash(b"payload")
    assert len(digest) == 16
    int(digest, 16)
