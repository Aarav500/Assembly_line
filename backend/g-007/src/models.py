from typing import Tuple
import torch
import torch.nn as nn


class TextClassifier(nn.Module):
    def __init__(self, vocab_size: int, embedding_dim: int = 128, hidden_dim: int = 256, num_layers: int = 2, bidirectional: bool = True, dropout: float = 0.2, num_classes: int = 2, pad_idx: int = 0):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embedding_dim, padding_idx=pad_idx)
        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
        )
        self.dropout = nn.Dropout(dropout)
        out_dim = hidden_dim * (2 if bidirectional else 1)
        self.fc = nn.Linear(out_dim, num_classes)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        # x: [B, T], lengths: [B]
        emb = self.embed(x)
        packed = nn.utils.rnn.pack_padded_sequence(emb, lengths.cpu(), batch_first=True, enforce_sorted=False)
        packed_out, (h_n, c_n) = self.lstm(packed)
        # Concatenate final forward and backward hidden states
        if self.lstm.bidirectional:
            h = torch.cat([h_n[-2], h_n[-1]], dim=-1)
        else:
            h = h_n[-1]
        h = self.dropout(h)
        logits = self.fc(h)
        return logits

    def get_arch(self) -> dict:
        return {
            "embedding_dim": self.embed.embedding_dim,
            "hidden_dim": self.lstm.hidden_size,
            "num_layers": self.lstm.num_layers,
            "bidirectional": self.lstm.bidirectional,
            "dropout": float(self.dropout.p),
        }

