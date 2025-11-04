import os
import time

# A placeholder model. Replace with your actual model call.
# For demonstration, we transform the prompt and optionally sleep to simulate latency.

def generate(prompt: str) -> str:
    # Optional artificial delay to mimic model latency
    delay_ms = int(os.getenv("MODEL_DELAY_MS", "0"))
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

    # Simple deterministic transformation to simulate an "answer"
    # In a real application, call your ML model here.
    answer = prompt.strip()
    if not answer:
        return ""

    # Simulate a response format
    return f"Answer: {answer[:2048]}"

