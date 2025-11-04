import os


def get_config():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    return {
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-secret-key'),
        # If IDEATER_IMPORT_ENDPOINT is set, client will POST to it with features list
        'IDEATER_IMPORT_ENDPOINT': os.getenv('IDEATER_IMPORT_ENDPOINT', '').strip() or None,
        'IDEATER_API_BASE': os.getenv('IDEATER_API_BASE', '').strip() or None,
        'IDEATER_API_TOKEN': os.getenv('IDEATER_API_TOKEN', '').strip() or None,
        'IDEATER_WORKSPACE_ID': os.getenv('IDEATER_WORKSPACE_ID', '').strip() or None,
        'IDEATER_WORKSPACE_URL': os.getenv('IDEATER_WORKSPACE_URL', '').strip() or None,
    }

