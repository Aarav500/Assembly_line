from typing import Dict
from PIL import Image, ImageChops
from pathlib import Path


def _normalize_sizes(img1: Image.Image, img2: Image.Image):
    w = max(img1.width, img2.width)
    h = max(img1.height, img2.height)
    if img1.size == (w, h) and img2.size == (w, h):
        return img1, img2
    bg = (255, 255, 255)
    new1 = Image.new("RGB", (w, h), bg)
    new2 = Image.new("RGB", (w, h), bg)
    new1.paste(img1, (0, 0))
    new2.paste(img2, (0, 0))
    return new1, new2


def compare_images(baseline_path: str, candidate_path: str, diff_path: str, threshold_percent: float = 2.0) -> Dict:
    base_path = Path(baseline_path)
    cand_path = Path(candidate_path)

    img_base = Image.open(base_path).convert("RGB")
    img_cand = Image.open(cand_path).convert("RGB")

    img_base, img_cand = _normalize_sizes(img_base, img_cand)

    diff = ImageChops.difference(img_base, img_cand)
    mask = diff.convert("L")

    total_pixels = mask.width * mask.height
    hist = mask.histogram()  # 256 bins
    zero_count = hist[0] if len(hist) > 0 else 0
    diff_pixels = total_pixels - zero_count
    mismatch_percent = (diff_pixels / total_pixels) * 100.0 if total_pixels else 0.0

    passed = mismatch_percent <= threshold_percent

    # Create overlay diff image: candidate highlighted in red where different
    cand_rgba = img_cand.convert("RGBA")
    # Convert mask to semi-transparent alpha mask
    semi_mask = mask.point(lambda p: 160 if p else 0)
    red_overlay = Image.new("RGBA", cand_rgba.size, (255, 0, 0, 160))
    cand_rgba.paste(red_overlay, (0, 0), semi_mask)

    out_path = Path(diff_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cand_rgba.save(out_path)

    return {
        "passed": passed,
        "threshold_percent": threshold_percent,
        "mismatch_percent": round(mismatch_percent, 4),
        "diff_pixels": int(diff_pixels),
        "total_pixels": int(total_pixels),
    }

