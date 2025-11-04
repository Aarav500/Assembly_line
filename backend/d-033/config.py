import os

class Config:
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8080"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    STORAGE_DIR = os.getenv("ATTESTATION_STORAGE_DIR", os.path.abspath(os.path.join(os.getcwd(), "attestations")))

    PRIV_KEY_PEM_FILE = os.getenv("ATTESTATION_PRIVATE_KEY_PEM_FILE")
    PRIV_KEY_B64 = os.getenv("ATTESTATION_PRIVATE_KEY_B64")
    SAVE_GENERATED_KEY_TO = os.getenv("ATTESTATION_SAVE_GENERATED_KEY_TO")

config = Config()

