from decimal import Decimal
from datetime import datetime
import uuid
from models import Pricing

# Basic default pricing (USD) for some common models; update as needed
DEFAULT_PRICING = {
    "openai": {
        # gpt-4o mini pricing example
        "gpt-4o-mini": {"input_per_1k_usd": 0.150, "output_per_1k_usd": 0.600, "currency": "USD"},
        # gpt-4o pricing example
        "gpt-4o": {"input_per_1k_usd": 5.00, "output_per_1k_usd": 15.00, "currency": "USD"},
        # gpt-3.5-turbo legacy example
        "gpt-3.5-turbo": {"input_per_1k_usd": 0.50, "output_per_1k_usd": 1.50, "currency": "USD"},
    },
    "anthropic": {
        "claude-3-haiku": {"input_per_1k_usd": 0.25, "output_per_1k_usd": 1.25, "currency": "USD"},
        "claude-3-opus": {"input_per_1k_usd": 15.00, "output_per_1k_usd": 75.00, "currency": "USD"},
    },
    "google": {
        "gemini-1.5-pro": {"input_per_1k_usd": 3.50, "output_per_1k_usd": 10.50, "currency": "USD"},
    }
}


def get_pricing(session, provider: str, model: str):
    # Try DB first
    p = session.query(Pricing).filter(Pricing.provider == provider, Pricing.model == model).one_or_none()
    if p is not None:
        return {
            "input_per_1k_usd": Decimal(str(p.input_per_1k_usd)),
            "output_per_1k_usd": Decimal(str(p.output_per_1k_usd)),
            "currency": p.currency,
        }
    # fallback to defaults
    prov = DEFAULT_PRICING.get(provider or "", {})
    if model in prov:
        rates = prov[model]
        return {
            "input_per_1k_usd": Decimal(str(rates.get("input_per_1k_usd", 0))),
            "output_per_1k_usd": Decimal(str(rates.get("output_per_1k_usd", 0))),
            "currency": rates.get("currency", "USD"),
        }
    return None


def calculate_cost_usd(prompt_tokens: int, completion_tokens: int, pricing: dict):
    input_rate = Decimal(str(pricing.get("input_per_1k_usd", 0)))
    output_rate = Decimal(str(pricing.get("output_per_1k_usd", 0)))
    pt = Decimal(prompt_tokens or 0)
    ct = Decimal(completion_tokens or 0)
    prompt_cost = (pt / Decimal(1000)) * input_rate
    completion_cost = (ct / Decimal(1000)) * output_rate
    total_cost = prompt_cost + completion_cost
    return {
        "prompt_cost_usd": float(prompt_cost),
        "completion_cost_usd": float(completion_cost),
        "total_cost_usd": float(total_cost),
    }


def upsert_pricing(session, provider: str, model: str, input_per_1k: float, output_per_1k: float, currency: str = "USD"):
    existing = session.query(Pricing).filter(Pricing.provider == provider, Pricing.model == model).one_or_none()
    now = datetime.utcnow()
    if existing:
        existing.input_per_1k_usd = Decimal(str(input_per_1k))
        existing.output_per_1k_usd = Decimal(str(output_per_1k))
        existing.currency = currency
        existing.updated_at = now
        session.add(existing)
    else:
        p = Pricing(
            id=str(uuid.uuid4()),
            provider=provider,
            model=model,
            input_per_1k_usd=Decimal(str(input_per_1k)),
            output_per_1k_usd=Decimal(str(output_per_1k)),
            currency=currency,
            updated_at=now
        )
        session.add(p)

