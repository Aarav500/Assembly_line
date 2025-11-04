from typing import Dict
import os
import torch
import torch.nn as nn

from .utils import load_package, save_package, file_size_mb
from .models import TextClassifier

try:
    from torch.ao.quantization import quantize_dynamic
except Exception:  # fallback for older torch
    from torch.quantization import quantize_dynamic


MODULE_TYPES = {nn.Linear, nn.LSTM}


def quantize_model(model_package_path: str, output_path: str, dtype: str = "qint8") -> Dict:
    pkg = load_package(model_package_path)
    arch = pkg["arch"]
    vocab = pkg["vocab"]

    model = TextClassifier(
        vocab_size=len(vocab["stoi"]),
        embedding_dim=arch["embedding_dim"],
        hidden_dim=arch["hidden_dim"],
        num_layers=arch["num_layers"],
        bidirectional=arch["bidirectional"],
        dropout=arch["dropout"],
        num_classes=2,
        pad_idx=0,
    )
    model.load_state_dict(pkg["state_dict"])
    model.eval()

    if dtype == "qint8":
        qdtype = torch.qint8
    elif dtype == "float16":
        # dynamic quantization equivalent for linear layers is not float16; so we handle cast
        qdtype = None
    else:
        qdtype = torch.qint8

    if qdtype is not None:
        qmodel = quantize_dynamic(model, {nn.Linear, nn.LSTM}, dtype=qdtype)
    else:
        # fp16 weights for linear layers only as a lightweight compression
        qmodel = model.half()

    # Save as a pickled quantized model object for actual disk size reduction
    out_pkg = {
        "model": qmodel,
        "vocab": vocab,
        "arch": arch,
        "meta": {"num_classes": 2, "quantized": True, "dtype": dtype}
    }
    save_package(output_path, out_pkg)

    in_size = file_size_mb(model_package_path)
    out_size = file_size_mb(output_path)
    return {
        "input_model_path": model_package_path,
        "quantized_model_path": output_path,
        "input_size_mb": round(in_size, 4),
        "output_size_mb": round(out_size, 4),
        "size_reduction_mb": round(in_size - out_size, 4),
        "reduction_ratio": round((1.0 - out_size / in_size) if in_size > 0 else 0.0, 4)
    }

