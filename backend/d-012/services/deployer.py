from typing import Optional, Dict, Any
from datetime import datetime
import os


class Deployer:
    def __init__(self, registry, monitor, incident_manager, log_buffer):
        self.registry = registry
        self.monitor = monitor
        self.incident_manager = incident_manager
        self.log = log_buffer

    def deploy(self, service: str, version: str) -> Dict[str, Any]:
        state = self.registry.get_or_create(service)
        previous_version = state.current_version
        self.log.add(service, 'INFO', 'Starting deployment', version=version, previous_version=previous_version)

        # Simulate applying deployment (set current version optimistically)
        self.registry.set_current_version(service, version)
        self.log.add(service, 'INFO', 'Applied version to target', version=version)

        # Post-deploy health check
        ok, details = self.monitor.health_check(service, version)
        if not ok:
            # Rollback
            rollback_to = state.last_good_version
            self.registry.rollback(service, rollback_to)
            self.log.add(service, 'ERROR', 'Health check failed, rolling back',
                         attempted_version=version, rollback_to=rollback_to, details=details)

            snapshot = self._build_root_cause_snapshot(
                service=service,
                attempted_version=version,
                previous_version=previous_version,
                rollback_to=rollback_to,
                health_details=details
            )
            incident_id = self.incident_manager.create_incident(
                service=service,
                attempted_version=version,
                previous_version=previous_version,
                rollback_version=rollback_to,
                snapshot=snapshot
            )
            return {
                'status': 'rolled_back',
                'service': service,
                'attempted_version': version,
                'rolled_back_to': rollback_to,
                'incident_id': incident_id,
                'health': details
            }

        # Success
        self.registry.mark_good(service, version)
        self.log.add(service, 'INFO', 'Deployment successful', version=version)
        return {
            'status': 'success',
            'service': service,
            'version': version,
            'health': details
        }

    def _build_root_cause_snapshot(self,
                                   service: str,
                                   attempted_version: str,
                                   previous_version: Optional[str],
                                   rollback_to: Optional[str],
                                   health_details: Dict[str, Any]):
        # Gather synthetic environment/config info
        env_snapshot = {
            'env': {
                'DEPLOY_ENV': os.getenv('DEPLOY_ENV', 'dev'),
                'HOSTNAME': os.getenv('HOSTNAME', 'localhost'),
            },
            'config_diff': {
                'summary': 'no-config-manager-integrated',
                'changes': []
            },
            'commit_refs': {
                'candidate_commit': f'{attempted_version}-sha',
                'previous_commit': f'{(previous_version or "none")}-sha'
            }
        }
        logs_tail = self.log.tail(service, n=50)
        snapshot = {
            'event_type': 'deploy_failure',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'service': service,
            'attempted_version': attempted_version,
            'previous_version': previous_version,
            'rolled_back_to': rollback_to,
            'health_check': health_details,
            'logs_tail': logs_tail,
            'environment': env_snapshot,
        }
        return snapshot

