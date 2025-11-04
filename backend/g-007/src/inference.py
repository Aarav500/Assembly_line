from typing import List, Dict
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from .dataset import Vocab, simple_tokenize, collate_pad, PAD_ID
from .models import TextClassifier
from .utils import load_package, timeit_sync


def _prepare_batch(vocab: Vocab, texts: List[str]):
    encoded = [(vocab.encode(t), 0) for t in texts]
    x, lengths, _ = collate_pad(encoded)
    return x, lengths


def _softmax_probs(logits: torch.Tensor):
    return torch.softmax(logits, dim=-1)


def _load_model_from_package(pkg_path: str):
    pkg = load_package(pkg_path)
    vocab = Vocab(stoi=pkg["vocab"]["stoi"], itos=pkg["vocab"]["itos"]) if isinstance(pkg.get("vocab"), dict) else Vocab(stoi=pkg["vocab"].stoi, itos=pkg["vocab"].itos)

    if "model" in pkg:  # quantized pickled model
        model = pkg["model"]
        model.eval()
        return model, vocab
    else:
        arch = pkg["arch"]
        model = TextClassifier(
            vocab_size=len(vocab),
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
        return model, vocab


def predict(model_package_path: str, texts: List[str], batch_size: int = 32, with_probs: bool = True) -> Dict:
    if not texts:
        return {"predictions": [], "latency_ms": None}

    device = torch.device("cpu")
    model, vocab = _load_model_from_package(model_package_path)
    model.to(device)

    # Warmup single pass for fair latency measurement
    _x, _lengths = _prepare_batch(vocab, texts[:min(2, len(texts))])
    with torch.no_grad():
        _ = model(_x.to(device), _lengths.to(device))

    def _run_once():
        preds = []
        probs_all = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            x, lengths = _prepare_batch(vocab, batch_texts)
            with torch.no_grad():
                logits = model(x.to(device), lengths.to(device))
                if with_probs:
                    probs = _softmax_probs(logits).cpu().numpy().tolist()
                p = logits.argmax(dim=-1).cpu().numpy().tolist()
            preds.extend(p)
            if with_probs:
                probs_all.extend(probs)
        return preds, probs_all

    # time measurement
    lat = timeit_sync(_run_once, repeat=5, warmup=1)
    preds, probs = _run_once()

    result = {"predictions": preds, "latency_ms": lat}
    if with_probs:
        result["probs"] = probs
    return result

