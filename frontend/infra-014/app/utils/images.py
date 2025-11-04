from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps

from app.config import DEFAULT_IMAGE_QUALITY


def _apply_exif_orientation(img: Image.Image) -> Image.Image:
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def _ensure_rgb_for_format(img: Image.Image, out_format: str) -> Image.Image:
    # JPEG does not support alpha channel; flatten on white background
    fmt = out_format.upper()
    if fmt in {"JPEG", "JPG"}:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            return bg
        if img.mode not in ("RGB",):
            return img.convert("RGB")
    # For other formats keep as is but convert palette images to RGBA/RGB
    if img.mode == "P":
        return img.convert("RGBA")
    return img


def resize_image(
    in_path: Path,
    out_path: Path,
    width: int,
    height: int,
    keep_aspect: bool = True,
    out_format: Optional[str] = None,
    quality: int = DEFAULT_IMAGE_QUALITY,
) -> Path:
    with Image.open(in_path) as im:
        im = _apply_exif_orientation(im)
        if keep_aspect:
            im.thumbnail((width, height), Image.LANCZOS)
        else:
            im = im.resize((width, height), Image.LANCZOS)

        fmt = out_format.upper() if out_format else (im.format or "PNG")
        im = _ensure_rgb_for_format(im, fmt)

        save_params = {}
        if fmt in {"JPEG", "JPG", "WEBP"}:
            save_params["quality"] = int(quality)
        if fmt == "JPEG":
            save_params["optimize"] = True
            save_params["progressive"] = True

        im.save(out_path, format=fmt, **save_params)
    return out_path


def convert_image(
    in_path: Path,
    out_path: Path,
    out_format: str,
    quality: int = DEFAULT_IMAGE_QUALITY,
) -> Path:
    with Image.open(in_path) as im:
        im = _apply_exif_orientation(im)
        fmt = out_format.upper()
        im = _ensure_rgb_for_format(im, fmt)

        save_params = {}
        if fmt in {"JPEG", "JPG", "WEBP"}:
            save_params["quality"] = int(quality)
        if fmt == "JPEG":
            save_params["optimize"] = True
            save_params["progressive"] = True

        im.save(out_path, format=fmt, **save_params)
    return out_path

