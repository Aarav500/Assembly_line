from pathlib import Path
from typing import List
from PIL import Image, ImageDraw, ImageFont
import textwrap


def images_to_pdf(image_paths: List[Path], out_pdf_path: Path) -> Path:
    images = []
    for p in image_paths:
        im = Image.open(p)
        if im.mode in ("RGBA", "LA"):
            im = im.convert("RGB")
        elif im.mode == "P":
            im = im.convert("RGB")
        images.append(im)

    if not images:
        raise ValueError("No images provided for PDF generation")

    first, rest = images[0], images[1:]
    first.save(out_pdf_path, "PDF", save_all=True, append_images=rest)

    for im in images:
        try:
            im.close()
        except Exception:
            pass

    return out_pdf_path


def text_to_pdf(
    text: str,
    out_pdf_path: Path,
    page_size: str = "A4",  # or "LETTER"
    font_size: int = 14,
    margin: int = 64,
    line_spacing: float = 1.3,
) -> Path:
    # Define page sizes in pixels (approx 150 PPI for reasonable file size)
    sizes = {
        "A4": (1240, 1754),     # ~ 8.27x11.69 at ~150ppi
        "LETTER": (1275, 1650), # ~ 8.5x11 at ~150ppi
    }
    page_w, page_h = sizes.get(page_size.upper(), sizes["A4"])

    # Try to load a truetype font if available, else fallback to default bitmap font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    usable_w = page_w - 2 * margin
    usable_h = page_h - 2 * margin

    def wrap_text(draw, text_block):
        lines = []
        for paragraph in text_block.splitlines() or [""]:
            if not paragraph:
                lines.append("")
                continue
            words = paragraph.split(" ")
            current = ""
            for word in words:
                tentative = (current + " " + word).strip()
                if draw.textlength(tentative, font=font) <= usable_w:
                    current = tentative
                else:
                    if current:
                        lines.append(current)
                        current = word
                    else:
                        # word longer than line, hard-wrap
                        for i in range(len(word)):
                            segment = word[: i + 1]
                            if draw.textlength(segment, font=font) > usable_w:
                                if i == 0:
                                    # cannot fit any char, force append
                                    lines.append(word)
                                    current = ""
                                else:
                                    lines.append(word[:i])
                                    current = word[i:]
                                break
                        else:
                            current = word
            lines.append(current)
        return lines

    pages = []
    draw_img = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(draw_img)
    lines = wrap_text(draw, text)
    line_height = int(font_size * line_spacing)

    y = margin
    page = Image.new("RGB", (page_w, page_h), "white")
    d = ImageDraw.Draw(page)

    for line in lines:
        if y + line_height > margin + usable_h:
            pages.append(page)
            page = Image.new("RGB", (page_w, page_h), "white")
            d = ImageDraw.Draw(page)
            y = margin
        d.text((margin, y), line, fill="black", font=font)
        y += line_height

    pages.append(page)

    # Save to PDF (multi-page)
    first, rest = pages[0], pages[1:]
    first.save(out_pdf_path, "PDF", save_all=True, append_images=rest)

    for p in pages:
        try:
            p.close()
        except Exception:
            pass

    return out_pdf_path

