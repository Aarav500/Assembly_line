from dataclasses import dataclass
from typing import Optional, Dict, Any
from utils.tokenizer import estimate_tokens

@dataclass
class RequestContext:
    user_id: Optional[str]
    prompt: str
    model_preference: Optional[str]  # 'local' | 'openai' | None
    hints: Dict[str, Any]
    max_tokens: Optional[int]
    temperature: Optional[float]
    remote_model: Optional[str]

@dataclass
class Decision:
    provider: str  # 'local' | 'openai'
    reason: str
    rules_applied: list
    constraints: dict
    model: Optional[str] = None

class PolicyEngine:
    def __init__(self, config):
        self.config = config

    def decide(self, ctx: RequestContext) -> Decision:
        rules_applied = []
        constraints = {}

        input_tokens = estimate_tokens(ctx.prompt)
        requested_max_tokens = ctx.max_tokens or 256
        safety_level = (ctx.hints.get('safety_level') if ctx.hints else None) or self.config.safety_default
        latency_pref = (ctx.hints.get('latency') if ctx.hints else None) or 'medium'  # low|medium|high
        cost_sensitivity = (ctx.hints.get('cost_sensitivity') if ctx.hints else None) or 'medium' # low|medium|high

        constraints['input_tokens'] = input_tokens
        constraints['requested_max_tokens'] = requested_max_tokens
        constraints['safety_level'] = safety_level
        constraints['latency_pref'] = latency_pref
        constraints['cost_sensitivity'] = cost_sensitivity

        # 1) Explicit preference overrides
        if ctx.model_preference in ('local', 'openai'):
            rules_applied.append('explicit_preference')
            provider = ctx.model_preference
            reason = f"Explicit model preference: {provider}"
            model = None
            if provider == 'openai':
                model = ctx.remote_model or self.config.default_openai_model
            return Decision(provider=provider, reason=reason, rules_applied=rules_applied, constraints=constraints, model=model)

        # 2) Safety first: high safety -> use remote with moderation if available
        if safety_level == 'high':
            rules_applied.append('safety_high_remote')
            provider = 'openai'
            model = ctx.remote_model or self.config.default_openai_model
            return Decision(provider=provider, reason='Safety high -> remote API with moderation', rules_applied=rules_applied, constraints=constraints, model=model)

        # 3) Token size threshold: if too big for local, route remote
        if input_tokens + requested_max_tokens > self.config.max_local_tokens + self.config.local_max_output_tokens:
            rules_applied.append('exceeds_local_token_capacity')
            provider = 'openai'
            model = ctx.remote_model or self.config.default_openai_model
            return Decision(provider=provider, reason='Input/output token requirement exceeds local capacity', rules_applied=rules_applied, constraints=constraints, model=model)

        # 4) Latency preference: if high latency sensitivity, prefer local (lower est. latency)
        if latency_pref == 'high':
            rules_applied.append('latency_sensitive_local')
            return Decision(provider='local', reason='High latency sensitivity -> prefer local', rules_applied=rules_applied, constraints=constraints)

        # 5) Cost sensitivity: if high, prefer local (zero marginal cost)
        if cost_sensitivity == 'high':
            rules_applied.append('cost_sensitive_local')
            return Decision(provider='local', reason='High cost sensitivity -> prefer local', rules_applied=rules_applied, constraints=constraints)

        # 6) Default heuristic: small inputs -> local, otherwise remote
        if input_tokens <= self.config.max_local_tokens:
            rules_applied.append('default_small_input_local')
            return Decision(provider='local', reason='Small input -> local by default', rules_applied=rules_applied, constraints=constraints)

        rules_applied.append('fallback_remote_default')
        provider = 'openai'
        model = ctx.remote_model or self.config.default_openai_model
        return Decision(provider=provider, reason='Fallback to remote default', rules_applied=rules_applied, constraints=constraints, model=model)

