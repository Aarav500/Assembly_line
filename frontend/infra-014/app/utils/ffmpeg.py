import subprocess
import shlex
import uuid
from pathlib import Path
from typing import Optional, List

from app.config import FFMPEG_BIN, MAX_FFMPEG_RUNTIME


class FFmpegError(RuntimeError):
    pass


def _run_ffmpeg(args: List[str], timeout: int = MAX_FFMPEG_RUNTIME) -> None:
    cmd = [FFMPEG_BIN, "-y"] + args
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:
        raise FFmpegError(f"FFmpeg binary not found: {FFMPEG_BIN}") from e
    except subprocess.TimeoutExpired as e:
        raise FFmpegError(f"FFmpeg timed out after {timeout} seconds") from e

    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.decode("utf-8", errors="ignore"))


def transcode_video(
    in_path: Path,
    out_path: Path,
    vcodec: str = "libx264",
    acodec: Optional[str] = "aac",
    crf: Optional[int] = 23,
    preset: Optional[str] = "medium",
    bitrate: Optional[str] = None,
    resolution: Optional[str] = None,  # e.g., "1280x720"
    fps: Optional[str] = None,
) -> Path:
    args: List[str] = [
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(in_path),
    ]

    if resolution:
        # Use scale filter to enforce resolution; keep aspect with force_original_aspect_ratio=decrease and pad
        try:
            w, h = resolution.lower().split("x")
            int(w); int(h)
            vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
            args += ["-vf", vf]
        except Exception:
            # fallback: let ffmpeg parse -s
            args += ["-s", resolution]

    if fps:
        args += ["-r", str(fps)]

    if vcodec:
        args += ["-c:v", vcodec]

    if crf is not None:
        args += ["-crf", str(crf)]

    if preset:
        args += ["-preset", preset]

    if bitrate:
        args += ["-b:v", str(bitrate)]

    if acodec is None:
        args += ["-an"]
    else:
        args += ["-c:a", acodec]

    args += [str(out_path)]

    _run_ffmpeg(args)
    return out_path


def extract_thumbnail(
    in_path: Path,
    out_path: Path,
    timestamp: str = "00:00:01.000",
    width: Optional[int] = None,
    height: Optional[int] = None,
    quality: int = 2,
) -> Path:
    args: List[str] = [
        "-hide_banner",
        "-loglevel", "error",
        "-ss", str(timestamp),
        "-i", str(in_path),
        "-frames:v", "1",
        "-q:v", str(quality),
    ]

    if width or height:
        w = width if width else -1
        h = height if height else -1
        # Keep aspect ratio while fitting within provided dimension(s)
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease"
        args += ["-vf", vf]

    args += [str(out_path)]

    _run_ffmpeg(args)
    return out_path

