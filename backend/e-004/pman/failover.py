import threading
import time
from .utils import run_cmd, pg_bin_path
from .state import State

class FailoverManager:
    def __init__(self, state: State, config: dict, cluster_manager):
        self.state = state
        self.config = config or {}
        self.cluster_manager = cluster_manager
        self._threads = {}
        self._locks = {}

    def configure_monitor(self, cluster_name, enabled: bool, interval: int = 5, fail_threshold: int = 3):
        c = self.state.get_cluster(cluster_name)
        if not c:
            raise FileNotFoundError('cluster not found')
        c['monitor'] = {'enabled': bool(enabled), 'interval': int(interval), 'fail_threshold': int(fail_threshold)}
        self.state.set_cluster(cluster_name, c)
        if enabled:
            self._start_thread(cluster_name)
        else:
            self._stop_thread(cluster_name)
        return {'status': 'monitor_' + ('enabled' if enabled else 'disabled'), 'cluster': cluster_name}

    def _start_thread(self, cluster_name):
        if cluster_name in self._threads and self._threads[cluster_name].is_alive():
            return
        lock = self._locks.setdefault(cluster_name, threading.RLock())
        t = threading.Thread(target=self._monitor_loop, args=(cluster_name, lock), daemon=True)
        self._threads[cluster_name] = t
        t.start()

    def _stop_thread(self, cluster_name):
        # Threads check state for enabled flag; they will exit naturally
        pass

    def _monitor_loop(self, cluster_name, lock):
        fail_count = 0
        while True:
            c = self.state.get_cluster(cluster_name)
            if not c or not c.get('monitor', {}).get('enabled'):
                return
            try:
                primary_name = c.get('current_primary', 'primary')
                node = c['nodes'][primary_name]
                pg_isready = pg_bin_path(c['pg_bin'], 'pg_isready')
                proc = run_cmd([pg_isready, '-h', node.get('host', '127.0.0.1'), '-p', str(node['port'])], check=False)
                if proc.returncode == 0:
                    fail_count = 0
                else:
                    fail_count += 1
                if fail_count >= int(c['monitor'].get('fail_threshold', 3)):
                    self._attempt_failover(cluster_name)
                    fail_count = 0
            except Exception:
                fail_count += 1
            time.sleep(int(c['monitor'].get('interval', 5)))

    def _attempt_failover(self, cluster_name):
        c = self.state.get_cluster(cluster_name)
        if not c:
            return
        # Choose a standby
        standby_name = None
        for n, info in c['nodes'].items():
            if info.get('role') == 'standby' and info.get('status') == 'running':
                standby_name = n
                break
        if not standby_name:
            # try to start any standby
            for n, info in c['nodes'].items():
                if info.get('role') == 'standby':
                    try:
                        self.cluster_manager.start_node(cluster_name, n)
                        standby_name = n
                        break
                    except Exception:
                        continue
        if standby_name:
            try:
                self.cluster_manager.promote_replica(cluster_name, standby_name)
            except Exception:
                pass

