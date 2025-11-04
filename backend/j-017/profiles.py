from database import db
from models import Profile

DEFAULT_PROFILES = [
    {
        "name": "creative",
        "description": "More imaginative, expansive responses with higher variability.",
        "temperature": 0.9,
        "top_p": 1.0,
        "presence_penalty": 0.6,
        "frequency_penalty": 0.2,
        "max_tokens": 400,
        "top_k": None,
        "seed": None,
    },
    {
        "name": "balanced",
        "description": "Balanced between creativity and determinism.",
        "temperature": 0.6,
        "top_p": 0.95,
        "presence_penalty": 0.2,
        "frequency_penalty": 0.1,
        "max_tokens": 350,
        "top_k": None,
        "seed": None,
    },
    {
        "name": "deterministic",
        "description": "Precise, concise, and repeatable responses with low randomness.",
        "temperature": 0.1,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "max_tokens": 300,
        "top_k": None,
        "seed": 42,
    },
]


def seed_default_profiles():
    if Profile.query.count() == 0:
        for data in DEFAULT_PROFILES:
            p = Profile(
                name=data["name"],
                description=data.get("description", ""),
                temperature=data.get("temperature", 0.7),
                top_p=data.get("top_p", 1.0),
                presence_penalty=data.get("presence_penalty", 0.0),
                frequency_penalty=data.get("frequency_penalty", 0.0),
                max_tokens=data.get("max_tokens", 300),
                top_k=data.get("top_k"),
                seed=data.get("seed"),
            )
            db.session.add(p)
        db.session.commit()

