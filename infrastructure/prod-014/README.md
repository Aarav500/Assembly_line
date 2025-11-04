Configuration Management with environment-specific configs, secret management (Vault/AWS Secrets Manager), and config validation.

Quick start:
- Set APP_ENV to one of: development, production, testing
- Put YAML configs under config/
- Use placeholders in configs for secrets and environment variables:
  - ${env:VAR_NAME|default}
  - ${vault:path/to/secret#key|default}
  - ${aws-sm:secret-id#json_key|default}
- Provide credentials via environment variables as needed:
  - For Vault: VAULT_ADDR, VAULT_TOKEN, VAULT_VERIFY (true/false)
  - For AWS: AWS_REGION (and any standard AWS credentials envs)

Commands:
- Validate config: python manage.py validate-config --env development --config-dir ./config
- Run server:     python manage.py runserver --env development --config-dir ./config

Endpoints:
- GET /health  -> {"status":"ok"}
- GET /config  -> returns sanitized current configuration

