import os

class Config:
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///alerts.db')
    MODEL_DIR = os.environ.get('MODEL_DIR', './models_store')
    # IsolationForest decision_function > 0 => inlier (considered noise). Override if needed.
    NOISE_DECISION_THRESHOLD = float(os.environ.get('NOISE_DECISION_THRESHOLD', '0.0'))
    # Correlation clustering parameters
    CLUSTER_EPS = float(os.environ.get('CLUSTER_EPS', '0.4'))  # cosine distance threshold
    CLUSTER_MIN_SAMPLES = int(os.environ.get('CLUSTER_MIN_SAMPLES', '2'))
    # Minimum alerts to train the noise model
    MIN_TRAIN_ALERTS = int(os.environ.get('MIN_TRAIN_ALERTS', '30'))

