import os
import json
import textwrap
import requests
from typing import Dict, Any


class LLMClient:
    def __init__(self, model: str = None, force_fake: bool = False):
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.api_base = os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
        self.force_fake = force_fake or not bool(self.api_key)
        # If no API key, we fallback to fake mode to allow local demo

    def generate_repo_files(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if self.force_fake:
            return self._fake_response()
        return self._openai_chat(system_prompt, user_prompt)

    def _openai_chat(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        url = f"{self.api_base}/chat/completions"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': self.model,
            'temperature': 0.2,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        }
        # Try to enforce JSON output if supported
        if os.environ.get('OPENAI_FORCE_JSON', 'true').lower() == 'true':
            payload['response_format'] = {'type': 'json_object'}

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text}")
        data = resp.json()
        try:
            content = data['choices'][0]['message']['content']
        except Exception:
            raise RuntimeError('OpenAI API response missing content')

        parsed = self._parse_json_strict(content)
        if not parsed or 'files' not in parsed:
            raise RuntimeError('LLM did not return JSON with a "files" array')
        return parsed

    @staticmethod
    def _parse_json_strict(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            # Try to extract the largest JSON object from the text
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass
            raise

    @staticmethod
    def _fake_response() -> Dict[str, Any]:
        # Minimal Flask app demo to show pipeline works without an API key
        files = [
            {
                'path': 'app.py',
                'content': textwrap.dedent('''\
                    from flask import Flask
                    app = Flask(__name__)

                    @app.route('/')
                    def hello():
                        return 'Hello from fake LLM generated repo!'

                    if __name__ == '__main__':
                        app.run(host='0.0.0.0', port=8081)
                ''').strip('\n')
            },
            {
                'path': 'requirements.txt',
                'content': 'flask\n'
            },
            {
                'path': 'README.md',
                'content': textwrap.dedent('''\
                    Example repo generated in fake mode. Run with:\n\n                    pip install -r requirements.txt\n                    python app.py\n                ''').strip('\n')
            }
        ]
        return {"files": files}

