import os
import random
from typing import Optional, Tuple, Dict, Any

from config import Config

# Try import OpenAI only when needed

def _get_openai_client():
    try:
        from openai import OpenAI
        api_key = Config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def _system_prompt_for_profile(profile_name: str) -> str:
    name = (profile_name or "").lower()
    if name == "creative":
        return (
            "You are a creative assistant. Offer imaginative, vivid, and engaging responses. "
            "Be bold with examples and analogies while staying coherent and helpful."
        )
    if name == "deterministic":
        return (
            "You are a precise and deterministic assistant. Provide concise, unambiguous, and factual responses. "
            "Avoid unnecessary embellishment."
        )
    return (
        "You are a helpful assistant. Balance clarity with a bit of color in your explanations."
    )


def _call_openai(message: str, profile, model_override: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client unavailable")

    model = model_override or Config.OPENAI_MODEL

    system_prompt = _system_prompt_for_profile(getattr(profile, 'name', ''))

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        temperature=float(getattr(profile, 'temperature', 0.7) or 0.7),
        top_p=float(getattr(profile, 'top_p', 1.0) or 1.0),
        presence_penalty=float(getattr(profile, 'presence_penalty', 0.0) or 0.0),
        frequency_penalty=float(getattr(profile, 'frequency_penalty', 0.0) or 0.0),
        max_tokens=int(getattr(profile, 'max_tokens', Config.DEFAULT_MAX_TOKENS) or Config.DEFAULT_MAX_TOKENS),
    )

    text = resp.choices[0].message.content
    usage = getattr(resp, 'usage', None)
    usage_dict = {
        "prompt_tokens": getattr(usage, 'prompt_tokens', None) if usage else None,
        "completion_tokens": getattr(usage, 'completion_tokens', None) if usage else None,
        "total_tokens": getattr(usage, 'total_tokens', None) if usage else None,
    }
    return text, usage_dict


def _call_echo(message: str, profile) -> Tuple[str, Dict[str, Any]]:
    # Very simple heuristic to emulate creativity vs determinism without external APIs
    temp = float(getattr(profile, 'temperature', 0.7) or 0.7)
    seed = getattr(profile, 'seed', None)
    rng = random.Random(seed if seed is not None else None)

    if temp <= 0.2:
        reply = f"Answer: {message.strip()}"
    elif temp <= 0.6:
        reply = f"Response: {message.strip()}\n\nSummary: {message.strip()[:80]}..."
    else:
        adjectives = ["vibrant", "evocative", "luminous", "imaginative", "whimsical", "spirited"]
        styles = ["poem", "short vignette", "metaphor", "storylet", "list of ideas"]
        adj = rng.choice(adjectives)
        style = rng.choice(styles)
        reply = (
            f"In a {adj} {style}, consider this: {message.strip()}\n"
            f"Idea spark: {rng.choice(['contrast', 'analogy', 'example', 'counterpoint'])}."
        )
    usage = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    return reply, usage


def generate_response(message: str, profile, model_override: Optional[str] = None) -> Dict[str, Any]:
    provider_choice = Config.AI_PROVIDER

    if provider_choice == 'openai' or (provider_choice == 'auto' and Config.OPENAI_API_KEY):
        try:
            text, usage = _call_openai(message, profile, model_override=model_override)
            provider = 'openai'
            model = model_override or Config.OPENAI_MODEL
            return {
                "provider": provider,
                "model": model,
                "reply": text,
                "usage": usage,
            }
        except Exception as e:
            # Fallback to echo if openai fails
            pass

    # Echo provider (no external calls)
    text, usage = _call_echo(message, profile)
    return {
        "provider": "echo",
        "model": None,
        "reply": text,
        "usage": usage,
    }

