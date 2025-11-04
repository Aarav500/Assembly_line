import json
import os
import platform
import requests
import subprocess

BASE = os.getenv('API_BASE', 'http://localhost:8000')


def pip_freeze_text():
    try:
        out = subprocess.check_output(['python', '-m', 'pip', 'freeze'], text=True)
        return out
    except Exception:
        return ''


def main():
    # 1) Register dataset
    ds = requests.post(f'{BASE}/datasets', json={
        'name': 'example-dataset',
        'version': '1.0',
        'uri': 's3://bucket/path/to/dataset.csv',
        'metadata': {'owner': 'ml-team', 'description': 'Sample dataset for demo'}
    }).json()
    print('Dataset:', ds)

    # 2) Register code version
    code = requests.post(f'{BASE}/code-versions', json={
        'repo_url': 'https://github.com/acme/ml-project',
        'commit_hash': 'deadbeefcafebabe1234567890abcdef12345678',
        'branch': 'main',
        'notes': 'Demo commit'
    }).json()
    print('CodeVersion:', code)

    # 3) Register environment
    env = requests.post(f'{BASE}/environments', json={
        'python_version': platform.python_version(),
        'pip_freeze': pip_freeze_text(),
        'docker_image': 'python:3.10-slim',
        'os_info': {'platform': platform.platform()},
    }).json()
    print('Environment:', env)

    # 4) Create run
    run = requests.post(f'{BASE}/runs', json={
        'name': 'demo-run',
        'status': 'running',
        'random_seed': 42,
        'parameters': {'lr': 0.001, 'epochs': 5},
        'code_version_id': code['id'],
        'environment_id': env['id'],
        'datasets': [{'dataset_id': ds['id'], 'role': 'train'}]
    }).json()
    print('Run:', run['id'])

    # 5) Upload artifact (simulated model file)
    model_path = 'demo-model.bin'
    with open(model_path, 'wb') as f:
        f.write(os.urandom(1024))
    with open(model_path, 'rb') as f:
        art = requests.post(f'{BASE}/artifacts', data={'run_id': run['id'], 'type': 'model', 'description': 'Demo model'}, files={'file': f}).json()
    print('Artifact:', art)

    # 6) Finish run
    finished = requests.post(f'{BASE}/runs/{run["id"]}/finish', json={'status': 'finished', 'metrics': {'accuracy': 0.9}}).json()
    print('Finished:', finished['status'])

    # 7) Create bundle
    bundle = requests.post(f'{BASE}/runs/{run["id"]}/bundle').json()
    print('Bundle:', bundle)


if __name__ == '__main__':
    main()

