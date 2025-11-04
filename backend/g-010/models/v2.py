import os
import random
import time
from .base import BaseModel


class ModelV2(BaseModel):
    def __init__(self, error_prob: float = 0.05):
        self.error_prob = max(0.0, min(1.0, float(error_prob)))
        slow_ms = os.getenv("MODEL_V2_ADDED_LATENCY_MS")
        self.added_latency_ms = float(slow_ms) if slow_ms else 0.0

    def predict(self, text: str):
        # Simulate slight additional latency compared to v1
        if self.added_latency_ms > 0:
            time.sleep(self.added_latency_ms / 1000.0)
        # Simulate occasional errors in the new version
        if random.random() < self.error_prob:
            raise RuntimeError("v2 transient error: simulated")
        lower = (text or "").lower()
        # Slightly different heuristic
        positive_keywords = ["good", "great", "awesome", "excelent", "minunat", "grozav"]
        negative_keywords = ["bad", "terrible", "awful", "nasol", "prost"]
        score = 0
        for w in positive_keywords:
            if w in lower:
                score += 1
        for w in negative_keywords:
            if w in lower:
                score -= 1
        sentiment = "positive" if score >= 0 else "negative"
        confidence = 0.55 + 0.1 * abs(score)
        return {
            "sentiment": sentiment,
            "confidence": round(min(0.99, confidence), 2),
        }

