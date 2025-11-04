import io
from typing import Dict, Iterable

from PIL import Image


def is_image_content_type(content_type: str | None) -> bool:
    return bool(content_type and content_type.lower().startswith("image/"))


def make_thumbnails(image_bytes: bytes, sizes: Iterable[int]) -> Dict[int, bytes]:
    output: Dict[int, bytes] = {}
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        for size in sizes:
            thumb = img.copy()
            thumb.thumbnail((size, size))
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=85)
            output[size] = buf.getvalue()
    return output

