from typing import Dict
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from .dataset import JsonlTextDataset, collate_pad, Vocab
from .models import TextClassifier
from .utils import set_seed, save_package, load_package, count_parameters
from .config import DEFAULT_STUDENT_CONFIG


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device):
    model.eval()
    ce = nn.CrossEntropyLoss()
    total = 0
    correct = 0
    loss_sum = 0.0
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


def distill_student(teacher_package_path: str, train_path: str, val_path: str, output_path: str, config: Dict = None):
    cfg = dict(DEFAULT_STUDENT_CONFIG)
    if config:
        cfg.update(config)

    set_seed(123)
    device = torch.device("cpu")

    # Load teacher package
    t_pkg = load_package(teacher_package_path)
    t_vocab = Vocab(stoi=t_pkg["vocab"]["stoi"], itos=t_pkg["vocab"]["itos"]) 

    # Data using teacher's vocab
    train_ds = JsonlTextDataset(train_path, vocab=t_vocab, build_vocab=False)
    val_ds = JsonlTextDataset(val_path, vocab=t_vocab, build_vocab=False)
    train_loader = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True, collate_fn=collate_pad)
    val_loader = DataLoader(val_ds, batch_size=cfg["batch_size"], shuffle=False, collate_fn=collate_pad)

    # Teacher model
    t_arch = t_pkg["arch"]
    teacher = TextClassifier(
        vocab_size=len(t_vocab),
        embedding_dim=t_arch["embedding_dim"],
        hidden_dim=t_arch["hidden_dim"],
        num_layers=t_arch["num_layers"],
        bidirectional=t_arch["bidirectional"],
        dropout=t_arch["dropout"],
        num_classes=2,
        pad_idx=0,
    ).to(device)
    teacher.load_state_dict(t_pkg["state_dict"])  # teacher is fp32
    teacher.eval()
    for p in teacher.parameters():
        p.requires_grad = False

    # Student model
    student = TextClassifier(
        vocab_size=len(t_vocab),
        embedding_dim=cfg["embedding_dim"],
        hidden_dim=cfg["hidden_dim"],
        num_layers=cfg["num_layers"],
        bidirectional=cfg["bidirectional"],
        dropout=cfg["dropout"],
        num_classes=2,
        pad_idx=0,
    ).to(device)

    optimizer = torch.optim.Adam(student.parameters(), lr=cfg["lr"])
    ce = nn.CrossEntropyLoss()
    kldiv = nn.KLDivLoss(reduction="batchmean")
    T = float(cfg["temperature"])
    alpha = float(cfg["alpha"])

    best_val_acc = 0.0
    history = []

    for epoch in range(1, cfg["epochs"] + 1):
        student.train()
        pbar = tqdm(train_loader, desc=f"Student Epoch {epoch}")
        total = 0
        correct = 0
        loss_sum = 0.0
        for x, lengths, y in pbar:
            x = x.to(device)
            lengths = lengths.to(device)
            y = y.to(device)
            optimizer.zero_grad()
            with torch.no_grad():
                t_logits = teacher(x, lengths)
            s_logits = student(x, lengths)
            loss_ce = ce(s_logits, y)
            s_log_probs_T = nn.functional.log_softmax(s_logits / T, dim=-1)
            t_probs_T = nn.functional.softmax(t_logits / T, dim=-1)
            loss_kd = kldiv(s_log_probs_T, t_probs_T) * (T * T)
            loss = alpha * loss_kd + (1.0 - alpha) * loss_ce
            loss.backward()
            torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
            optimizer.step()

            with torch.no_grad():
                preds = s_logits.argmax(dim=-1)
                correct += (preds == y).sum().item()
                total += y.size(0)
                loss_sum += loss.item() * y.size(0)
            pbar.set_postfix({"loss": f"{loss_sum/max(1,total):.4f}", "acc": f"{correct/max(1,total):.4f}"})

        val_metrics = evaluate(student, val_loader, device)
        epoch_metrics = {"epoch": epoch, "train_loss": loss_sum / max(1, total), "train_acc": correct / max(1, total), "val_loss": val_metrics["loss"], "val_acc": val_metrics["acc"]}
        history.append(epoch_metrics)
        if val_metrics["acc"] >= best_val_acc:
            best_val_acc = val_metrics["acc"]
            package = {
                "arch": student.get_arch(),
                "vocab": {"stoi": t_vocab.stoi, "itos": t_vocab.itos},
                "state_dict": student.state_dict(),
                "meta": {"num_classes": 2, "type": "student"}
            }
            save_package(output_path, package)

    return {
        "model_path": output_path,
        "params": count_parameters(student),
        "best_val_acc": best_val_acc,
        "history": history,
    }

