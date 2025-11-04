import os


def get_config():
    cfg = {}
    cfg['API_TOKEN'] = os.environ.get('AUDIT_API_TOKEN', 'dev-token')
    data_dir = os.environ.get('DATA_DIR', 'data')
    cfg['DATABASE'] = os.environ.get('DATABASE_URL', os.path.join(data_dir, 'app.db'))
    cfg['EXPORT_DIR'] = os.environ.get('EXPORT_DIR', os.path.join(data_dir, 'exports'))
    cfg['SIGNING_KEY'] = os.environ.get('SIGNING_KEY', '')
    cfg['APP_VERSION'] = os.environ.get('APP_VERSION', '1.0.0')
    return cfg

