import os
import shutil
import subprocess
import threading
import time
import datetime as dt
import json
import tempfile
from queue import Queue
from typing import Dict, Any, Optional

import boto3

from .storage import BuildStorage


def _hcl_quote(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _hcl_render(value):
    if isinstance(value, str):
        return _hcl_quote(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(_hcl_render(v) for v in value) + ']'
    if isinstance(value, dict):
        items = []
        for k, v in value.items():
            key = k if isinstance(k, str) else str(k)
            items.append(f"{key} = {_hcl_render(v)}")
        return '{ ' + ', '.join(items) + ' }'
    if value is None:
        return 'null'
    return _hcl_quote(str(value))


def dict_to_pkrvars_hcl(d: Dict[str, Any]) -> str:
    lines = []
    for k, v in d.items():
        lines.append(f"{k} = {_hcl_render(v)}")
    return '\n'.join(lines) + '\n'


class BuildManager:
    def __init__(self, storage: BuildStorage, base_dir: str, builds_dir: str, templates_dir: str, default_settings: Optional[Dict[str, Any]] = None):
        self.storage = storage
        self.base_dir = base_dir
        self.builds_dir = builds_dir
        self.templates_dir = templates_dir
        self.default_settings = default_settings or {}
        self.queue = Queue()
        self._worker_started = False
        self._start_worker()

    def _start_worker(self):
        if self._worker_started:
            return
        t = threading.Thread(target=self._worker_loop, daemon=True)
        t.start()
        self._worker_started = True

    def _worker_loop(self):
        while True:
            job = self.queue.get()
            try:
                self._run_build(job)
            except Exception as e:
                # Best-effort failure record
                build = self.storage.get_build(job['build_id']) or {}
                build['status'] = 'failed'
                build['error'] = str(e)
                build['finished_at'] = dt.datetime.utcnow().isoformat() + 'Z'
                self.storage.save_build(build['build_id'], build)
            finally:
                self.queue.task_done()

    def enqueue_build(self, build_id: str, pipeline: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None, ami_suffix: Optional[str] = None) -> Dict[str, Any]:
        overrides = overrides or {}
        template_path = pipeline.get('template')
        if not template_path:
            raise ValueError('Pipeline template is required')
        if not os.path.isabs(template_path):
            template_path = os.path.join(self.base_dir, template_path)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f'Template not found: {template_path}')

        variables = {}
        # Merge order: defaults -> pipeline -> overrides
        variables.update(self.default_settings.get('variables', {}))
        variables.update(pipeline.get('variables', {}))
        variables.update(overrides)

        ami_prefix = variables.get('ami_name_prefix') or pipeline.get('name', 'golden-image')
        timestamp = dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')
        if ami_suffix:
            ami_name = f"{ami_prefix}-{ami_suffix}-{timestamp}"
        else:
            ami_name = f"{ami_prefix}-{timestamp}"
        variables['ami_name'] = ami_name

        region = variables.get('region') or self.default_settings.get('region')
        if not region:
            raise ValueError('region must be provided in settings or pipeline variables')

        # Build record
        log_dir = os.path.join(self.builds_dir, build_id)
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'build.log')

        build_record = {
            'id': build_id,
            'pipeline_name': pipeline.get('name'),
            'template': template_path,
            'variables': variables,
            'status': 'queued',
            'created_at': dt.datetime.utcnow().isoformat() + 'Z',
            'started_at': None,
            'finished_at': None,
            'log_path': log_path,
            'ami_id': None,
            'ami_name': ami_name,
            'region': region,
        }
        self.storage.save_build(build_id, build_record)

        self.queue.put({
            'build_id': build_id,
            'record': build_record,
        })

        return {
            'build_id': build_id,
            'status': 'queued',
            'log_path': log_path,
        }

    def _run_build(self, job: Dict[str, Any]):
        build_id = job['build_id']
        record = self.storage.get_build(build_id)
        if not record:
            return

        record['status'] = 'running'
        record['started_at'] = dt.datetime.utcnow().isoformat() + 'Z'
        self.storage.save_build(build_id, record)

        log_path = record['log_path']
        template_path = record['template']
        variables = record['variables']
        region = record['region']

        # Prepare var-file
        vars_dir = os.path.dirname(log_path)
        var_file = os.path.join(vars_dir, 'vars.auto.pkrvars.hcl')
        with open(var_file, 'w', encoding='utf-8') as f:
            f.write(dict_to_pkrvars_hcl(variables))

        env = os.environ.copy()
        # Ensure AWS region for boto3 and Packer
        env.setdefault('AWS_REGION', region)
        env.setdefault('AWS_DEFAULT_REGION', region)

        # Run packer init and build
        with open(log_path, 'w', encoding='utf-8') as logf:
            logf.write(f"[info] Starting build {build_id} at {record['started_at']}\n")
            logf.write(f"[info] Template: {template_path}\n")
            logf.write(f"[info] Var file: {var_file}\n")
            logf.flush()

            if shutil.which('packer') is None:
                logf.write('[error] Packer executable not found in PATH.\n')
                record['status'] = 'failed'
                record['finished_at'] = dt.datetime.utcnow().isoformat() + 'Z'
                self.storage.save_build(build_id, record)
                return

            # packer init
            init_cmd = ['packer', 'init', template_path]
            logf.write('[cmd] ' + ' '.join(init_cmd) + '\n')
            logf.flush()
            p_init = subprocess.Popen(init_cmd, stdout=logf, stderr=logf, cwd=os.path.dirname(template_path), env=env)
            rc_init = p_init.wait()
            if rc_init != 0:
                logf.write(f'[error] packer init failed with code {rc_init}\n')
                record['status'] = 'failed'
                record['finished_at'] = dt.datetime.utcnow().isoformat() + 'Z'
                self.storage.save_build(build_id, record)
                return

            # packer build
            build_cmd = ['packer', 'build', '-color=false', f'-var-file={var_file}', template_path]
            logf.write('[cmd] ' + ' '.join(build_cmd) + '\n')
            logf.flush()
            p_build = subprocess.Popen(build_cmd, stdout=logf, stderr=logf, cwd=os.path.dirname(template_path), env=env)
            rc_build = p_build.wait()

            if rc_build != 0:
                logf.write(f'[error] packer build failed with code {rc_build}\n')
                record['status'] = 'failed'
                record['finished_at'] = dt.datetime.utcnow().isoformat() + 'Z'
                self.storage.save_build(build_id, record)
                return

            # On success, resolve AMI ID by name
            ami_name = record['ami_name']
            try:
                session = boto3.session.Session(region_name=region)
                ec2 = session.client('ec2')
                resp = ec2.describe_images(Filters=[{'Name': 'name', 'Values': [ami_name]}], Owners=['self'])
                images = resp.get('Images', [])
                if images:
                    # choose most recent by CreationDate
                    images.sort(key=lambda x: x.get('CreationDate', ''), reverse=True)
                    ami_id = images[0].get('ImageId')
                    record['ami_id'] = ami_id
                    logf.write(f'[info] AMI created: {ami_id} (name={ami_name})\n')
                else:
                    logf.write(f'[warn] AMI with name {ami_name} not found via describe_images.\n')
            except Exception as e:
                logf.write(f'[warn] Failed to resolve AMI ID: {e}\n')

            record['status'] = 'succeeded'
            record['finished_at'] = dt.datetime.utcnow().isoformat() + 'Z'
            self.storage.save_build(build_id, record)
            logf.write(f"[info] Build {build_id} finished at {record['finished_at']}\n")
            logf.flush()

