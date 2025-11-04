import base64
import io
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image


def _ensure_3ch(img: Image.Image, channels: int) -> Image.Image:
    if channels == 1:
        if img.mode != "L":
            img = img.convert("L")
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
    return img


def load_image_from_request(data: bytes | str, target_hw: Tuple[int, int], channels: int) -> np.ndarray:
    # Accept raw bytes or base64 string
    if isinstance(data, str):
        try:
            data = base64.b64decode(data)
        except Exception:
            # assume it's a path-like string? Not supported here; expect base64
            raise ValueError("image_base64 must be base64-encoded string")
    buf = io.BytesIO(data)
    img = Image.open(buf)
    img = _ensure_3ch(img, channels)
    img = img.resize((target_hw[1], target_hw[0]), Image.BILINEAR)
    arr = np.array(img)
    if channels == 1 and arr.ndim == 2:
        arr = arr[..., None]
    return arr


def preprocess_to_input_dtype(
    x: np.ndarray,
    target_hw: Tuple[int, int],
    channels: int,
    input_dtype: np.dtype,
    input_quant_params: Tuple[float, int],
    preprocessing_cfg: Optional[Dict] = None,
) -> np.ndarray:
    preprocessing_cfg = preprocessing_cfg or {}

    # If input is image array but not target size, resize with PIL for fidelity
    if x.ndim >= 2:
        h, w = target_hw
        if x.ndim == 3:
            cur_h, cur_w = x.shape[0], x.shape[1]
        elif x.ndim == 4:
            cur_h, cur_w = x.shape[1], x.shape[2]
        else:
            cur_h, cur_w = h, w
        if (cur_h, cur_w) != (h, w):
            # Use PIL for resizing
            img = Image.fromarray(x.astype(np.uint8)) if x.dtype != np.uint8 else Image.fromarray(x)
            img = img.resize((w, h), Image.BILINEAR)
            x = np.array(img)
    # Ensure channels
    if channels == 1 and x.ndim == 3 and x.shape[-1] != 1:
        if x.ndim == 3 and x.shape[-1] == 3:
            # Convert RGB -> grayscale by luminance
            x = (0.2989 * x[..., 0] + 0.5870 * x[..., 1] + 0.1140 * x[..., 2]).astype(np.float32)
            x = x[..., None]
    elif channels == 3 and x.ndim == 3 and x.shape[-1] == 1:
        x = np.repeat(x, 3, axis=-1)

    # Normalization settings
    norm = preprocessing_cfg.get("normalize", {})
    mean = np.array(norm.get("mean", [0.0, 0.0, 0.0]), dtype=np.float32)
    std = np.array(norm.get("std", [1.0, 1.0, 1.0]), dtype=np.float32)
    scale = float(norm.get("scale", 255.0))  # typical 255 for 0..255 -> 0..1

    # Convert to desired dtype
    if input_dtype == np.uint8:
        # feed raw 0..255
        if x.dtype != np.uint8:
            x = np.clip(x, 0, 255).astype(np.uint8)
        return x
    elif input_dtype == np.int8:
        # compute real-valued normalized input then quantize using input quant params
        real = x.astype(np.float32) / scale
        # channel-wise mean/std
        if real.ndim == 3 and mean.size == 3:
            real = (real - mean) / std
        else:
            real = (real - float(mean.mean())) / float(std.mean())
        q_scale, q_zero = input_quant_params or (0.0, 0)
        if not q_scale:
            # fallback to range [-1,1] -> int8
            real = np.clip(real, -1.0, 1.0)
            q = np.round(real * 127.0).astype(np.int8)
        else:
            q = np.round(real / float(q_scale) + float(q_zero)).astype(np.int16)
            q = np.clip(q, -128, 127).astype(np.int8)
        return q
    else:
        # float input: normalize to [0,1] and apply mean/std
        f = x.astype(np.float32) / scale
        if f.ndim == 3 and mean.size == 3:
            f = (f - mean) / std
        else:
            f = (f - float(mean.mean())) / float(std.mean())
        return f.astype(np.float32)

