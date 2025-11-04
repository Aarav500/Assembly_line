import time
from typing import Dict, Any
from providers.local_client import LocalClient
from providers.openai_client import OpenAIClient
from utils.tokenizer import estimate_tokens

class HybridRouter:
    def __init__(self, config):
        self.config = config
        self.local = LocalClient(config)
        self.remote = OpenAIClient(config)

    def _estimate_cost(self, provider: str, input_tokens: int, output_tokens: int) -> float:
        if provider == 'local':
            return 0.0
        # OpenAI cost estimate
        input_cost = (input_tokens / 1000.0) * self.config.cost_openai_input_per_1k
        output_cost = (output_tokens / 1000.0) * self.config.cost_openai_output_per_1k
        return round(input_cost + output_cost, 6)

    def route_and_execute(self, ctx, decision) -> Dict[str, Any]:
        prompt = ctx.prompt
        max_tokens = min(ctx.max_tokens or 256, 2048)
        temperature = ctx.temperature if ctx.temperature is not None else 0.7

        if decision.provider == 'local':
            t0 = time.time()
            out = self.local.generate(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
            latency_ms = int((time.time() - t0) * 1000)
            input_tokens = estimate_tokens(prompt)
            output_tokens = estimate_tokens(out)
            return {
                'provider': 'local',
                'model': self.config.local_model_name,
                'output': out,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'cost_estimated_usd': self._estimate_cost('local', input_tokens, output_tokens)
                },
                'latency_ms': latency_ms
            }
        elif decision.provider == 'openai':
            t0 = time.time()
            out, used_model, usage = self.remote.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                model=decision.model
            )
            latency_ms = int((time.time() - t0) * 1000)
            input_tokens = usage.get('input_tokens') or estimate_tokens(prompt)
            output_tokens = usage.get('output_tokens') or estimate_tokens(out)
            return {
                'provider': 'openai',
                'model': used_model,
                'output': out,
                'usage': {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'total_tokens': input_tokens + output_tokens,
                    'cost_estimated_usd': self._estimate_cost('openai', input_tokens, output_tokens)
                },
                'latency_ms': latency_ms
            }
        else:
            raise ValueError(f"Unknown provider: {decision.provider}")

