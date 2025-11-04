DEFAULT_TEACHER_CONFIG = {
    "embedding_dim": 128,
    "hidden_dim": 256,
    "num_layers": 2,
    "bidirectional": True,
    "dropout": 0.2,
    "lr": 3e-3,
    "batch_size": 64,
    "epochs": 4,
    "max_vocab_size": 20000,
}

DEFAULT_STUDENT_CONFIG = {
    "embedding_dim": 64,
    "hidden_dim": 128,
    "num_layers": 1,
    "bidirectional": True,
    "dropout": 0.1,
    "lr": 3e-3,
    "batch_size": 64,
    "epochs": 4,
    "temperature": 2.0,
    "alpha": 0.7,
}

