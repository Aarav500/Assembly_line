import os
import shutil
from .state import State
from .utils import ensure_dir, run_cmd, write_append, write_overwrite, now_ts, random_password, find_node, pg_bin_path

class ClusterManager:
    def __init__(self, state: State, config: dict):
        self.state = state
        self.config = config or {}

    def list_clusters(self):
        return self.state.list_clusters()

    def get_cluster(self, name):
        return self.state.get_cluster(name)

    def get_current_primary_node_name(self, name):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError("cluster not found")
        return c.get('current_primary', 'primary')

    def create_cluster(self, name, base_dir, pg_bin, port, replication_password=None, archive_dir=None, initdb_args=None):
        if self.state.get_cluster(name):
            raise RuntimeError("cluster already exists")
        base_dir = os.path.abspath(base_dir)
        ensure_dir(base_dir)
        archive_dir = archive_dir or os.path.join(base_dir, 'archive')
        ensure_dir(archive_dir)
        logs_dir = ensure_dir(os.path.join(base_dir, 'logs'))
        data_dir = os.path.join(base_dir, 'primary')
        backups_dir = ensure_dir(os.path.join(base_dir, 'backups'))
        replicas_dir = ensure_dir(os.path.join(base_dir, 'replicas'))
        repl_pass = replication_password or random_password()
        cluster = {
            'name': name,
            'pg_bin': os.path.abspath(pg_bin),
            'base_dir': base_dir,
            'archive_dir': archive_dir,
            'backups_dir': backups_dir,
            'replicas_dir': replicas_dir,
            'logs_dir': logs_dir,
            'replication': {'user': 'replicator', 'password': repl_pass},
            'current_primary': 'primary',
            'nodes': {
                'primary': {
                    'role': 'primary',
                    'data_dir': data_dir,
                    'port': int(port),
                    'host': '127.0.0.1',
                    'status': 'not_initialized'
                }
            },
            'monitor': {'enabled': False, 'interval': 5, 'fail_threshold': 3}
        }
        self.state.set_cluster(name, cluster)
        return cluster

    def delete_cluster(self, name):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError("cluster not found")
        # Try to stop all nodes
        for node_name in list(c.get('nodes', {}).keys()):
            try:
                self.stop_node(name, node_name)
            except Exception:
                pass
        # Delete from disk but keep cautious
        base_dir = c['base_dir']
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir, ignore_errors=True)
        self.state.delete_cluster(name)

    def _configure_primary_conf(self, cluster, node):
        data_dir = node['data_dir']
        port = node['port']
        archive_dir = cluster['archive_dir']
        conf_path = os.path.join(data_dir, 'postgresql.conf')
        append = "\n".join([
            f"listen_addresses = '*'",
            f"port = {port}",
            f"wal_level = 'replica'",
            f"max_wal_senders = 10",
            f"archive_mode = on",
            f"archive_command = 'test ! -f {archive_dir}/%f && cp %p {archive_dir}/%f'",
            f"hot_standby = on",
            "" 
        ]) + "\n"
        write_append(conf_path, "\n# Managed by MPG\n" + append)
        # hba
        hba_path = os.path.join(data_dir, 'pg_hba.conf')
        hba = "\n".join([
            "# Managed by MPG",
            "local   all             all                                     trust",
            "host    all             all             127.0.0.1/32            trust",
            "host    all             all             ::1/128                 trust",
            "host    all             all             0.0.0.0/0               md5",
            f"host    replication     {cluster['replication']['user']}     0.0.0.0/0               md5",
            ""
        ]) + "\n"
        write_append(hba_path, hba)

    def init_primary(self, name):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError("cluster not found")
        node = c['nodes']['primary']
        data_dir = node['data_dir']
        if os.path.exists(os.path.join(data_dir, 'PG_VERSION')):
            raise RuntimeError("primary already initialized")
        os.makedirs(data_dir, exist_ok=True)
        initdb = pg_bin_path(c['pg_bin'], 'initdb')
        initdb_args = self.config.get('initdb_args', [])
        run_cmd([initdb, '-D', data_dir] + (initdb_args or []))
        self._configure_primary_conf(c, node)
        # Start primary
        self.start_node(name, 'primary')
        # Create replication user
        psql = pg_bin_path(c['pg_bin'], 'psql')
        repl_user = c['replication']['user']
        repl_pass = c['replication']['password']
        port = node['port']
        sql = f"CREATE ROLE {repl_user} WITH REPLICATION LOGIN ENCRYPTED PASSWORD '{repl_pass}';"
        run_cmd([psql, '-h', '127.0.0.1', '-p', str(port), '-U', 'postgres', '-d', 'postgres', '-c', sql], env={'PGPASSWORD': ''}, check=True)
        # Update status
        c['nodes']['primary']['status'] = 'running'
        self.state.set_cluster(name, c)
        return {'status': 'initialized', 'cluster': c}

    def start_node(self, name, node_name):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError('cluster not found')
        node = find_node(c, node_name)
        pg_ctl = pg_bin_path(c['pg_bin'], 'pg_ctl')
        log_file = os.path.join(c['logs_dir'], f"{node_name}.log")
        run_cmd([pg_ctl, '-D', node['data_dir'], '-l', log_file, 'start'])
        # Optionally wait for readiness
        pg_isready = pg_bin_path(c['pg_bin'], 'pg_isready')
        run_cmd([pg_isready, '-h', node.get('host', '127.0.0.1'), '-p', str(node['port'])], check=False)
        node['status'] = 'running'
        c['nodes'][node_name] = node
        self.state.set_cluster(name, c)
        return {'status': 'started', 'node': node_name}

    def stop_node(self, name, node_name):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError('cluster not found')
        node = find_node(c, node_name)
        pg_ctl = pg_bin_path(c['pg_bin'], 'pg_ctl')
        run_cmd([pg_ctl, '-D', node['data_dir'], 'stop', '-m', 'fast'], check=False)
        node['status'] = 'stopped'
        c['nodes'][node_name] = node
        self.state.set_cluster(name, c)
        return {'status': 'stopped', 'node': node_name}

    def create_replica(self, name, replica_name, port):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError('cluster not found')
        if replica_name in c['nodes']:
            raise RuntimeError('replica already exists')
        primary_name = c.get('current_primary', 'primary')
        primary = find_node(c, primary_name)
        if primary['status'] != 'running':
            raise RuntimeError('primary not running')
        replica_dir = os.path.join(c['replicas_dir'], replica_name)
        os.makedirs(replica_dir, exist_ok=True)
        # Base backup
        pg_basebackup = pg_bin_path(c['pg_bin'], 'pg_basebackup')
        env = {'PGPASSWORD': c['replication']['password']}
        args = [
            pg_basebackup,
            '-h', primary.get('host', '127.0.0.1'),
            '-p', str(primary['port']),
            '-D', replica_dir,
            '-U', c['replication']['user'],
            '-X', 'stream',
            '-R'
        ]
        run_cmd(args, env=env)
        # Configure port and hot_standby
        conf_path = os.path.join(replica_dir, 'postgresql.conf')
        write_append(conf_path, f"\n# Managed by MPG\nport = {int(port)}\nhot_standby = on\n")
        # Start replica
        c['nodes'][replica_name] = {
            'role': 'standby',
            'data_dir': replica_dir,
            'port': int(port),
            'host': '127.0.0.1',
            'status': 'created'
        }
        self.state.set_cluster(name, c)
        self.start_node(name, replica_name)
        return {'status': 'replica_created', 'replica': replica_name}

    def promote_replica(self, name, replica_name):
        c = self.state.get_cluster(name)
        if not c:
            raise FileNotFoundError('cluster not found')
        replica = find_node(c, replica_name)
        if replica['role'] != 'standby':
            raise RuntimeError('node is not a standby')
        if replica['status'] != 'running':
            raise RuntimeError('standby not running')
        pg_ctl = pg_bin_path(c['pg_bin'], 'pg_ctl')
        run_cmd([pg_ctl, '-D', replica['data_dir'], 'promote'])
        c['current_primary'] = replica_name
        self.state.set_cluster(name, c)
        return {'status': 'promoted', 'new_primary': replica_name}

