import os
import subprocess
import time
import random
import string


def run_cmd(args, env=None, cwd=None, check=True, text=True, input_data=None):
    final_env = os.environ.copy()
    if env:
        final_env.update(env)
    proc = subprocess.run(
        args,
        env=final_env,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=text,
        input=input_data,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\nstdout: {proc.stdout}\nstderr: {proc.stderr}")
    return proc


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def write_append(path, text):
    with open(path, 'a') as f:
        f.write(text)


def write_overwrite(path, text):
    with open(path, 'w') as f:
        f.write(text)


def now_ts():
    return time.strftime('%Y%m%d-%H%M%S')


def random_password(length=24):
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.SystemRandom().choice(alphabet) for _ in range(length))


def find_node(state_cluster, node_name):
    nodes = state_cluster.get('nodes', {})
    if node_name not in nodes:
        raise FileNotFoundError(f"node not found: {node_name}")
    return nodes[node_name]


def pg_bin_path(bin_dir, binary):
    path = os.path.join(bin_dir, binary)
    if os.name == 'nt':
        path += '.exe'
    return path

