import os

SETTINGS = {
    'DATASETS_DIR': os.environ.get('DATASETS_DIR', os.path.join(os.getcwd(), 'data', 'datasets')),
    'OUTPUTS_DIR': os.environ.get('OUTPUTS_DIR', os.path.join(os.getcwd(), 'outputs')),
    'LOGS_DIR': os.environ.get('LOGS_DIR', os.path.join(os.getcwd(), 'logs')),
}

