from __future__ import annotations

import base64
import hashlib
import urllib.parse
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.providers.base import ImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "BMP"}
BAIDU_MAX_ENCODED_BYTES = 8 * 1024 * 1024
TENCENT_MAX_BASE64_BYTES = 10 * 1024 * 1024
MIN_SIDE_PIXELS = 15
BAIDU_MAX_SIDE = 4096
MAX_SIDE_ANY = 10000


def image_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _encode_jpeg(image: Image.Image) -> bytes:
    if image.mode in ("RGBA", "LA", "P", "PA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    out = BytesIO()
    image.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def _encoded_size(encoded: bytes, provider: str) -> int:
    if provider == "local":
        return len(encoded)
    b64 = base64.b64encode(encoded).decode("ascii")
    if provider == "tencent":
        return len(b64)
    return len(urllib.parse.urlencode({"image": b64}).encode("utf-8"))


def _limit_bytes(provider: str, max_upload_bytes: int) -> int:
    if provider == "local":
        return max_upload_bytes
    if provider == "tencent":
        return TENCENT_MAX_BASE64_BYTES
    return BAIDU_MAX_ENCODED_BYTES


def _limit_side(provider: str) -> int:
    if provider in ("tencent", "local"):
        return MAX_SIDE_ANY
    return BAIDU_MAX_SIDE


def normalize_image(data: bytes, provider: str, max_bytes: int, max_pixels: int) -> bytes:
    """Validate, rotate and re-encode an upload into a vendor-safe JPEG."""
    if not data:
        raise ImageError("empty image")
    if len(data) > max_bytes:
        raise ImageError("image exceeds the upload size limit")

    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(BytesIO(data)) as probe:
            width, height = probe.size
            fmt = probe.format
            if width * height > max_pixels or max(width, height) > MAX_SIDE_ANY:
                raise ImageError("image pixel dimensions exceed the limit")
            if fmt not in ALLOWED_FORMATS:
                raise ImageError("unsupported image format")
            probe.verify()
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageError("file is not a decodable image") from exc
    except Image.DecompressionBombError as exc:  # pragma: no cover - defensive
        raise ImageError("image pixel dimensions exceed the limit") from exc

    try:
        with Image.open(BytesIO(data)) as decoded:
            decoded.load()
            image = ImageOps.exif_transpose(decoded)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            if image.width < MIN_SIDE_PIXELS or image.height < MIN_SIDE_PIXELS:
                raise ImageError("image is too small for the provider")
            return _fit_limits(image, provider, max_bytes)
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageError("file is not a decodable image") from exc


def _fit_limits(image: Image.Image, provider: str, max_upload_bytes: int) -> bytes:
    max_side = _limit_side(provider)
    max_encoded = _limit_bytes(provider, max_upload_bytes)
    scale = min(1.0, max_side / max(image.width, image.height))
    for _ in range(12):
        width = max(1, int(image.width * scale))
        height = max(1, int(image.height * scale))
        if min(width, height) < MIN_SIDE_PIXELS:
            raise ImageError("image is too small after scaling")
        candidate = image if scale >= 0.999 else image.resize((width, height), Image.Resampling.LANCZOS)
        encoded = _encode_jpeg(candidate)
        if _encoded_size(encoded, provider) <= max_encoded:
            return encoded
        if min(width, height) <= MIN_SIDE_PIXELS:
            break
        scale *= 0.85
    raise ImageError("image cannot be fitted into the provider limits")
