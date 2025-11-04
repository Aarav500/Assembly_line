import os

LABELS = ["pos", "neg"]
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 5))

DATA_PATH = os.environ.get("DATA_PATH", os.path.join("data", "data.json"))
MODEL_PATH = os.environ.get("MODEL_PATH", os.path.join("models", "model.joblib"))

