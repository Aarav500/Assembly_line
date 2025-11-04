import os
import shutil
from .utils import ensure_dir, run_cmd, write_append, write_overwrite, now_ts, pg_bin_path
from .state import State

class PITRManager:
    def __init__(self, state: State, config: dict):
        self.state = state
        self.config = config or {}

    def create_base_backup(self, name, label=None):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError('cluster not found')
        primary_name = c.get('current_primary', 'primary')
        primary = c['nodes'][primary_name]
        if primary['status'] != 'running':
            raise RuntimeError('primary not running')
        ts = now_ts()
        backup_name = f"backup_{label}_{ts}" if label else f"backup_{ts}"
        backup_dir = os.path.join(c['backups_dir'], backup_name)
        ensure_dir(backup_dir)
        pg_basebackup = pg_bin_path(c['pg_bin'], 'pg_basebackup')
        env = {'PGPASSWORD': c['replication']['password']}
        args = [
            pg_basebackup,
            '-h', primary.get('host', '127.0.0.1'),
            '-p', str(primary['port']),
            '-D', backup_dir,
            '-U', c['replication']['user'],
            '-X', 'stream'
        ]
        run_cmd(args, env=env)
        return {'status': 'backup_complete', 'backup_name': backup_name, 'backup_dir': backup_dir}

    def restore_to_time(self, name, backup_name, target_time, new_name, port):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError('cluster not found')
        source_backup = os.path.join(c['backups_dir'], backup_name)
        if not os.path.isdir(source_backup):
            raise FileNotFoundError('backup not found')
        new_dir = os.path.join(c['base_dir'], f"pitr_{new_name}")
        if os.path.exists(new_dir):
            raise RuntimeError('target data dir already exists')
        shutil.copytree(source_backup, new_dir)
        # Configure restore from archive
        archive_dir = c['archive_dir']
        # Create recovery.signal
        open(os.path.join(new_dir, 'recovery.signal'), 'a').close()
        # Append auto.conf for recovery settings
        auto_conf = os.path.join(new_dir, 'postgresql.auto.conf')
        write_append(auto_conf, f"\n# Managed by MPG PITR\nrestore_command = 'cp {archive_dir}/%f \"%p\"'\nrecovery_target_time = '{target_time}'\nrecovery_target_action = 'promote'\nport = {int(port)}\n")
        # Ensure hot_standby
        conf_path = os.path.join(new_dir, 'postgresql.conf')
        write_append(conf_path, f"\n# Managed by MPG PITR\nhot_standby = on\nlisten_addresses='*'\n")
        # Register node in cluster
        node_entry = {
            'role': 'pitr',
            'data_dir': new_dir,
            'port': int(port),
            'host': '127.0.0.1',
            'status': 'created'
        }
        c['nodes'][new_name] = node_entry
        self.state.set_cluster(name, c)
        # Start the restored node
        pg_ctl = pg_bin_path(c['pg_bin'], 'pg_ctl')
        log_file = os.path.join(c['logs_dir'], f"{new_name}.log")
        run_cmd([pg_ctl, '-D', new_dir, '-l', log_file, 'start'])
        node_entry['status'] = 'running'
        c['nodes'][new_name] = node_entry
        self.state.set_cluster(name, c)
        return {
            'status': 'pitr_recovery_started',
            'node': new_name,
            'data_dir': new_dir,
            'port': port,
            'note': 'Instance will recover to target_time using archived WAL and then promote.'
        }

