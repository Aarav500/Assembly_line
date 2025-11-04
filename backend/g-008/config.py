import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        # Routing defaults
        self.default_remote_provider = os.getenv('DEFAULT_REMOTE_PROVIDER', 'openai')
        self.default_openai_model = os.getenv('DEFAULT_OPENAI_MODEL', 'gpt-4o-mini')

        # Policy thresholds
        self.max_local_tokens = int(os.getenv('MAX_LOCAL_TOKENS', '512'))
        self.safety_default = os.getenv('SAFETY_DEFAULT', 'medium')  # low|medium|high

        # Latency estimates (ms)
        self.latency_local_ms_est = int(os.getenv('LATENCY_LOCAL_MS_EST', '60'))
        self.latency_remote_ms_est = int(os.getenv('LATENCY_REMOTE_MS_EST', '450'))

        # Cost estimates (USD per 1k tokens)
        # Defaults are placeholders; override via env for your models
        self.cost_openai_input_per_1k = float(os.getenv('COST_OPENAI_INPUT_PER_1K', '0.003'))
        self.cost_openai_output_per_1k = float(os.getenv('COST_OPENAI_OUTPUT_PER_1K', '0.006'))

        # API keys
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')

        # Moderation
        self.enable_openai_moderation = os.getenv('ENABLE_OPENAI_MODERATION', '1') == '1'
        self.openai_moderation_model = os.getenv('OPENAI_MODERATION_MODEL', 'omni-moderation-latest')

        # Local model config (placeholder)
        self.local_model_name = os.getenv('LOCAL_MODEL_NAME', 'toy-local')
        self.local_max_output_tokens = int(os.getenv('LOCAL_MAX_OUTPUT_TOKENS', '256'))

        # Logging/Tracing
        self.enable_debug_logging = os.getenv('ENABLE_DEBUG_LOGGING', '0') == '1'

