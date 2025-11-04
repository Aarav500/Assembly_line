import json
from typing import List, Dict, Tuple
import torch
from torch.utils.data import Dataset, DataLoader


SPECIAL_TOKENS = {"<pad>": 0, "<unk>": 1}
PAD_ID = 0
UNK_ID = 1


def simple_tokenize(text: str) -> List[str]:
    return text.lower().strip().split()


class Vocab:
    def __init__(self, stoi: Dict[str, int], itos: List[str]):
        self.stoi = stoi
        self.itos = itos

    @classmethod
    def build(cls, texts: List[str], max_size: int = 20000, min_freq: int = 1):
        from collections import Counter
        counter = Counter()
        for t in texts:
            counter.update(simple_tokenize(t))
        # Reserve ids for special tokens
        stoi = dict(SPECIAL_TOKENS)
        itos = [None] * len(SPECIAL_TOKENS)
        itos[PAD_ID] = "<pad>"
        itos[UNK_ID] = "<unk>"
        for tok, freq in counter.most_common():
            if freq < min_freq:
                continue
            if tok in stoi:
                continue
            if len(stoi) >= max_size:
                break
            stoi[tok] = len(stoi)
            itos.append(tok)
        return cls(stoi, itos)

    def encode(self, text: str) -> List[int]:
        return [self.stoi.get(t, UNK_ID) for t in simple_tokenize(text)]

    def __len__(self):
        return len(self.stoi)


class JsonlTextDataset(Dataset):
    def __init__(self, path: str, vocab: Vocab = None, build_vocab: bool = False, max_vocab_size: int = 20000):
        self.samples = []
        texts = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                ex = json.loads(line)
                text = ex["text"]
                label = int(ex["label"])  # 0/1
                self.samples.append((text, label))
                texts.append(text)
        if vocab is None and build_vocab:
            self.vocab = Vocab.build(texts, max_size=max_vocab_size)
        else:
            assert vocab is not None, "Vocab must be provided when build_vocab=False"
            self.vocab = vocab

        self.encoded = [(self.vocab.encode(t), y) for t, y in self.samples]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.encoded[idx]


def collate_pad(batch: List[Tuple[List[int], int]]):
    # batch: list of (ids, label)
    lengths = torch.tensor([len(ids) for ids, _ in batch], dtype=torch.long)
    max_len = int(lengths.max().item()) if len(batch) > 0 else 0
    inputs = torch.full((len(batch), max_len), PAD_ID, dtype=torch.long)
    labels = torch.tensor([y for _, y in batch], dtype=torch.long)
    for i, (ids, _) in enumerate(batch):
        if len(ids) == 0:
            continue
        inputs[i, :len(ids)] = torch.tensor(ids, dtype=torch.long)
    return inputs, lengths, labels


def make_dataloaders(train_path: str, val_path: str, batch_size: int, max_vocab_size: int = 20000):
    train_ds = JsonlTextDataset(train_path, vocab=None, build_vocab=True, max_vocab_size=max_vocab_size)
    vocab = train_ds.vocab
    val_ds = JsonlTextDataset(val_path, vocab=vocab, build_vocab=False)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_pad)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_pad)
    return train_loader, val_loader, vocab

