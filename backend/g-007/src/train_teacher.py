from typing import Dict
import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from .dataset import make_dataloaders
from .models import TextClassifier
from .utils import set_seed, save_package, count_parameters
from .config import DEFAULT_TEACHER_CONFIG


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> Dict[str, float]:
    model.eval()
    total = 0
    correct = 0
    loss_sum = 0.0
    ce = nn.CrossEntropyLoss()
    with torch.no_grad():
        for x, lengths, y in loader:
            x = x.to(device)
            lengths = lengths.to(device)
            y = y.to(device)
            logits = model(x, lengths)
            loss = ce(logits, y)
            loss_sum += loss.item() * y.size(0)
            preds = logits.argmax(dim=-1)
            correct += (preds == y).sum().item()
            total += y.size(0)
    return {"loss": loss_sum / max(1, total), "acc": correct / max(1, total)}


def train_teacher(train_path: str, val_path: str, output_path: str, config: Dict = None) -> Dict:
    cfg = dict(DEFAULT_TEACHER_CONFIG)
    if config:
        cfg.update(config)

    set_seed(42)
    device = torch.device("cpu")

    train_loader, val_loader, vocab = make_dataloaders(train_path, val_path, batch_size=cfg["batch_size"], max_vocab_size=cfg["max_vocab_size"])

    model = TextClassifier(
        vocab_size=len(vocab),
        embedding_dim=cfg["embedding_dim"],
        hidden_dim=cfg["hidden_dim"],
        num_layers=cfg["num_layers"],
        bidirectional=cfg["bidirectional"],
        dropout=cfg["dropout"],
        num_classes=2,
        pad_idx=0,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"])
    ce = nn.CrossEntropyLoss()

    best_val_acc = 0.0
    history = []

    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        pbar = tqdm(train_loader, desc=f"Teacher Epoch {epoch}")
        total = 0
        correct = 0
        loss_sum = 0.0
        for x, lengths, y in pbar:
            x = x.to(device)
            lengths = lengths.to(device)
            y = y.to(device)
            optimizer.zero_grad()
            logits = model(x, lengths)
            loss = ce(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            with torch.no_grad():
                preds = logits.argmax(dim=-1)
                correct += (preds == y).sum().item()
                total += y.size(0)
                loss_sum += loss.item() * y.size(0)
            pbar.set_postfix({"loss": f"{loss_sum/max(1,total):.4f}", "acc": f"{correct/max(1,total):.4f}"})
        val_metrics = evaluate(model, val_loader, device)
        epoch_metrics = {"epoch": epoch, "train_loss": loss_sum / max(1, total), "train_acc": correct / max(1, total), "val_loss": val_metrics["loss"], "val_acc": val_metrics["acc"]}
        history.append(epoch_metrics)
        if val_metrics["acc"] >= best_val_acc:
            best_val_acc = val_metrics["acc"]
            package = {
                "arch": model.get_arch(),
                "vocab": {"stoi": vocab.stoi, "itos": vocab.itos},
                "state_dict": model.state_dict(),
                "meta": {"num_classes": 2, "type": "teacher"}
            }
            save_package(output_path, package)

    return {
        "model_path": output_path,
        "params": count_parameters(model),
        "best_val_acc": best_val_acc,
        "history": history,
    }

