from typing import Callable, Dict, Any
import time

class Playbook:
    def __init__(self, id: str, name: str, description: str, risk: str, auto_approve: bool, execute: Callable[[Dict[str, Any], Callable[[str], None]], Dict[str, Any]]):
        self.id = id
        self.name = name
        self.description = description
        self.risk = risk
        self.auto_approve = auto_approve
        self._execute = execute
        self.mapped_alerts: list[str] = []

    def execute(self, context: Dict[str, Any], logger: Callable[[str], None]) -> Dict[str, Any]:
        return self._execute(context, logger)


# Example execution functions (simulated) ------------------------------------

def pb_restart_service(context, log):
    service = context.get('service', 'unknown-service')
    dry_run = bool(context.get('dry_run', False))
    log(f"Validating service '{service}' status")
    time.sleep(0.2)
    if dry_run:
        log("Dry run enabled: would restart service")
        return {'success': True, 'action': 'restart', 'service': service, 'dry_run': True}
    log(f"Attempting to restart service '{service}'")
    time.sleep(0.5)
    log(f"Service '{service}' restarted successfully")
    return {'success': True, 'action': 'restart', 'service': service}


def pb_clear_disk_space(context, log):
    path = context.get('path', '/')
    target_free_gb = float(context.get('target_free_gb', 5))
    log(f"Assessing disk usage at {path}")
    time.sleep(0.2)
    log("Identifying large files and caches")
    time.sleep(0.2)
    simulated_freed = min(target_free_gb, 3.0)  # pretend we could only free some
    if simulated_freed < target_free_gb:
        log(f"Warning: could only free {simulated_freed}GB out of {target_free_gb}GB target")
    time.sleep(0.2)
    success = simulated_freed > 0.5
    return {'success': success, 'action': 'clear_disk', 'path': path, 'freed_gb': simulated_freed, 'target_free_gb': target_free_gb}


def pb_scale_replicas(context, log):
    deployment = context.get('deployment', 'api')
    desired = int(context.get('replicas', 3))
    max_safe = int(context.get('max_safe', 10))
    log(f"Verifying current capacity for deployment '{deployment}'")
    time.sleep(0.2)
    if desired > max_safe:
        log(f"Desired replicas {desired} exceed max safe {max_safe}. Aborting.")
        return {'success': False, 'error': 'exceeds_max_safe', 'deployment': deployment, 'requested': desired, 'max_safe': max_safe}
    log(f"Scaling '{deployment}' to {desired} replicas")
    time.sleep(0.4)
    log("Scale operation completed")
    return {'success': True, 'action': 'scale', 'deployment': deployment, 'replicas': desired}


# Registry and alert mapping --------------------------------------------------

registry: Dict[str, Playbook] = {}

def register(pb: Playbook):
    registry[pb.id] = pb


register(Playbook(
    id='restart_service',
    name='Restart Service',
    description='Restart a given systemd or orchestrated service.',
    risk='low',
    auto_approve=True,
    execute=pb_restart_service
))

register(Playbook(
    id='clear_disk_space',
    name='Clear Disk Space',
    description='Remove caches and rotate logs to free disk space.',
    risk='medium',
    auto_approve=False,
    execute=pb_clear_disk_space
))

register(Playbook(
    id='scale_replicas',
    name='Scale Replicas',
    description='Scale application replicas to handle high load.',
    risk='high',
    auto_approve=False,
    execute=pb_scale_replicas
))

# Map alert types to playbooks
alert_to_playbook: Dict[str, str] = {
    'service_down': 'restart_service',
    'disk_full': 'clear_disk_space',
    'high_load': 'scale_replicas',
}

# populate mapped_alerts for display
for alert, pbid in alert_to_playbook.items():
    if pbid in registry:
        registry[pbid].mapped_alerts.append(alert)


def match_playbook_for_alert(alert_type: str) -> Playbook | None:
    pbid = alert_to_playbook.get(alert_type)
    return registry.get(pbid)


def get_playbook_by_id(pbid: str) -> Playbook | None:
    return registry.get(pbid)

