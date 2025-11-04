import os
import random
import time


def run_llm(prompt_text: str, provider: str = 'mock', model: str | None = None) -> dict:
    provider = (provider or 'mock').lower()

    if provider == 'openai':
        try:
            # Lazy import to keep optional dependency
            from openai import OpenAI
            client = OpenAI()
            chosen_model = model or os.getenv('LLM_MODEL', 'gpt-4o-mini')
            start = time.time()
            try:
                resp = client.chat.completions.create(
                    model=chosen_model,
                    messages=[{"role": "user", "content": prompt_text}],
                    temperature=float(os.getenv('LLM_TEMPERATURE', '0.2')),
                )
                output_text = resp.choices[0].message.content
                return {
                    'output_text': output_text,
                    'model': chosen_model,
                    'provider': 'openai',
                    'error': None,
                    'elapsed': time.time() - start,
                }
            except Exception as e:
                return {
                    'output_text': '',
                    'model': chosen_model,
                    'provider': 'openai',
                    'error': str(e),
                }
        except Exception as e:
            # Fallback to mock if openai SDK not available or misconfigured
            return _mock_llm(prompt_text)

    # default mock
    return _mock_llm(prompt_text)


def _mock_llm(prompt_text: str) -> dict:
    # Simulate processing time
    time.sleep(random.uniform(0.05, 0.25))
    # Simple deterministic transformation for repeatability
    preview = prompt_text[:200]
    reversed_preview = preview[::-1]
    output = (
        "MOCK_RESPONSE\n"
        "Echo (first 200 chars reversed):\n" + reversed_preview + "\n\n"
        "Summary: length=" + str(len(prompt_text)) + " chars."
    )
    return {
        'output_text': output,
        'model': 'mock-echo-v1',
        'provider': 'mock',
        'error': None,
    }

