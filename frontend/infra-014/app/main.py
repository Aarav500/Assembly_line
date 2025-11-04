import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.config import TEMP_DIR
from app.utils import ffmpeg as ffm
from app.utils import images as img
from app.utils import pdf

app = FastAPI(title="File Processing Service", version="1.0.0")


# Helpers

def _tmp_path(suffix: str) -> Path:
    return TEMP_DIR / f"{uuid.uuid4().hex}{suffix}"


def _save_upload_to_temp(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "").suffix or ""
    tmp_path = _tmp_path(suffix)
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return tmp_path


def _schedule_cleanup(bg: BackgroundTasks, *paths: Path) -> None:
    for p in paths:
        if not p:
            continue
        def _rm(path: Path):
            try:
                if path.exists():
                    path.unlink(missing_ok=True)
            except Exception:
                pass
        bg.add_task(_rm, p)


# Routes

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/image/resize")
async def image_resize(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
    keep_aspect: bool = Form(True),
    out_format: Optional[str] = Form(None),
    quality: int = Form(85),
):
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="width and height must be positive")

    in_path = _save_upload_to_temp(file)

    fmt = (out_format or Path(file.filename or "").suffix.replace(".", "")).lower() or "png"
    if fmt in ("jpg",):
        fmt = "jpeg"
    out_path = _tmp_path(f".{fmt}")

    try:
        img.resize_image(in_path, out_path, width, height, keep_aspect=keep_aspect, out_format=fmt, quality=quality)
    except Exception as e:
        _schedule_cleanup(background_tasks, in_path)
        raise HTTPException(status_code=400, detail=f"Image resize failed: {str(e)}")

    _schedule_cleanup(background_tasks, in_path, out_path)
    media_type = f"image/{'jpeg' if fmt == 'jpg' else fmt}"
    return FileResponse(path=out_path, filename=f"resized.{fmt}", media_type=media_type, background=background_tasks)


@app.post("/image/convert")
async def image_convert(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    out_format: str = Form(...),
    quality: int = Form(85),
):
    fmt = out_format.lower()
    if fmt == "jpg":
        fmt = "jpeg"

    in_path = _save_upload_to_temp(file)
    out_path = _tmp_path(f".{fmt}")

    try:
        img.convert_image(in_path, out_path, fmt, quality=quality)
    except Exception as e:
        _schedule_cleanup(background_tasks, in_path)
        raise HTTPException(status_code=400, detail=f"Image convert failed: {str(e)}")

    _schedule_cleanup(background_tasks, in_path, out_path)
    media_type = f"image/{fmt}"
    return FileResponse(path=out_path, filename=f"converted.{fmt}", media_type=media_type, background=background_tasks)


@app.post("/video/transcode")
async def video_transcode(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    vcodec: str = Form("libx264"),
    acodec: Optional[str] = Form("aac"),
    crf: int = Form(23),
    preset: str = Form("medium"),
    bitrate: Optional[str] = Form(None),
    resolution: Optional[str] = Form(None),  # e.g., 1280x720
    fps: Optional[str] = Form(None),
    container: str = Form("mp4"),
):
    cont = container.lower().lstrip(".")
    if cont not in {"mp4", "mkv", "mov", "webm"}:
        raise HTTPException(status_code=400, detail="Unsupported container; use mp4, mkv, mov, or webm")

    in_path = _save_upload_to_temp(file)
    out_path = _tmp_path(f".{cont}")

    try:
        ffm.transcode_video(
            in_path,
            out_path,
            vcodec=vcodec,
            acodec=acodec,
            crf=crf,
            preset=preset,
            bitrate=bitrate,
            resolution=resolution,
            fps=fps,
        )
    except Exception as e:
        _schedule_cleanup(background_tasks, in_path)
        raise HTTPException(status_code=400, detail=f"Video transcode failed: {str(e)}")

    _schedule_cleanup(background_tasks, in_path, out_path)
    media_type = {
        "mp4": "video/mp4",
        "mkv": "video/x-matroska",
        "mov": "video/quicktime",
        "webm": "video/webm",
    }.get(cont, "application/octet-stream")

    return FileResponse(path=out_path, filename=f"transcoded.{cont}", media_type=media_type, background=background_tasks)


@app.post("/video/thumbnail")
async def video_thumbnail(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    timestamp: str = Form("00:00:01.000"),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    out_format: str = Form("jpg"),
):
    fmt = out_format.lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in {"jpeg", "png", "webp"}:
        raise HTTPException(status_code=400, detail="Unsupported output format; use jpeg, png, or webp")

    in_path = _save_upload_to_temp(file)
    out_path = _tmp_path(f".{fmt}")

    try:
        ffm.extract_thumbnail(in_path, out_path, timestamp=timestamp, width=width, height=height)
    except Exception as e:
        _schedule_cleanup(background_tasks, in_path)
        raise HTTPException(status_code=400, detail=f"Thumbnail extraction failed: {str(e)}")

    _schedule_cleanup(background_tasks, in_path, out_path)
    media_type = f"image/{fmt}"
    return FileResponse(path=out_path, filename=f"thumbnail.{fmt}", media_type=media_type, background=background_tasks)


@app.post("/pdf/from-images")
async def pdf_from_images(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No images provided")

    temp_inputs: List[Path] = []
    try:
        for f in files:
            temp_inputs.append(_save_upload_to_temp(f))
    except Exception as e:
        for p in temp_inputs:
            try: p.unlink(missing_ok=True)
            except Exception: pass
        raise HTTPException(status_code=400, detail=f"Failed to read uploads: {str(e)}")

    out_path = _tmp_path(".pdf")
    try:
        pdf.images_to_pdf(temp_inputs, out_path)
    except Exception as e:
        for p in temp_inputs:
            try: p.unlink(missing_ok=True)
            except Exception: pass
        raise HTTPException(status_code=400, detail=f"PDF generation failed: {str(e)}")

    # Schedule cleanup
    _schedule_cleanup(background_tasks, out_path, *temp_inputs)
    return FileResponse(path=out_path, filename="merged.pdf", media_type="application/pdf", background=background_tasks)


@app.post("/pdf/from-text")
async def pdf_from_text(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    page_size: str = Form("A4"),
    font_size: int = Form(14),
):
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    out_path = _tmp_path(".pdf")
    try:
        pdf.text_to_pdf(text, out_path, page_size=page_size, font_size=font_size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF generation failed: {str(e)}")

    _schedule_cleanup(background_tasks, out_path)
    return FileResponse(path=out_path, filename="document.pdf", media_type="application/pdf", background=background_tasks)

