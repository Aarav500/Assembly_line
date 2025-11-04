from .base import BaseModel


class ModelV1(BaseModel):
    def predict(self, text: str):
        text = text or ""
        # A trivial deterministic model for demonstration
        lower = text.lower()
        sentiment = "positive" if "good" in lower or "great" in lower else "negative"
        return {
            "sentiment": sentiment,
            "confidence": 0.9 if sentiment == "positive" else 0.6,
        }

