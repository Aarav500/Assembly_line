import math
import time
from typing import Dict, List, Tuple

from .config import Config
from .state import ClusterState, Deployment, Pod, Node


class AutoScaler:
    def __init__(self, config: Config, state: ClusterState, pool_manager):
        self.config = config
        self.state = state
        self.pool_manager = pool_manager

    def _desired_replicas(self, dep: Deployment) -> int:
        if dep.target_rps_per_replica <= 0:
            return dep.min_replicas
        raw = dep.observed_rps / dep.target_rps_per_replica
        desired = math.ceil(raw * self.config.scale_up_sensitivity)
        desired = max(dep.min_replicas, min(dep.max_replicas, desired))
        return desired

    def _current_replicas(self, dep: Deployment) -> Tuple[int, int, int]:
        running = sum(1 for p in self.state.pods.values() if p.deployment == dep.name and p.phase == "Running")
        pending = sum(1 for p in self.state.pods.values() if p.deployment == dep.name and p.phase == "Pending")
        preempted = sum(1 for p in self.state.pods.values() if p.deployment == dep.name and p.phase == "Preempted")
        return running, pending, preempted

    def _spawn_pods(self, dep: Deployment, count: int):
        for _ in range(count):
            self.state.add_pod(deployment=dep.name)

    def _terminate_excess_pods(self, dep: Deployment, excess: int):
        # Prefer to remove pending first, then running from spot pool, then on-demand
        if excess <= 0:
            return
        # Remove pending pods
        for p in list(self.state.pods.values()):
            if excess <= 0:
                break
            if p.deployment == dep.name and p.phase == "Pending":
                self.state.remove_pod(p.id)
                excess -= 1
        if excess <= 0:
            return
        # Next remove running pods from spot
        spot_nodes = {n.id for n in self.state.nodes.values() if n.pool == self.config.spot_pool_name}
        for p in list(self.state.pods.values()):
            if excess <= 0:
                break
            if p.deployment == dep.name and p.phase == "Running" and p.node_id in spot_nodes:
                node = self.state.nodes.get(p.node_id)
                if node:
                    node.used_gpus = max(0, node.used_gpus - 1)
                self.state.remove_pod(p.id)
                excess -= 1
        if excess <= 0:
            return
        # Finally remove running pods from on-demand
        for p in list(self.state.pods.values()):
            if excess <= 0:
                break
            if p.deployment == dep.name and p.phase == "Running":
                node = self.state.nodes.get(p.node_id)
                if node:
                    node.used_gpus = max(0, node.used_gpus - 1)
                self.state.remove_pod(p.id)
                excess -= 1

    def _schedule_pending(self):
        # strives to place pending pods respecting spot fraction caps
        pending = [p for p in self.state.pods.values() if p.phase == "Pending"]
        if not pending:
            return
        # Build per-deployment stats
        per_dep_running_nodes: Dict[str, Dict[str, int]] = {}
        for dep in self.state.deployments.values():
            on = self.state.total_running_pods_in_pool(self.config.on_demand_pool_name)
            sp = self.state.total_running_pods_in_pool(self.config.spot_pool_name)
            per_dep_running_nodes[dep.name] = {"on": on, "sp": sp}
        # Prefer to schedule each pod considering its deployment policy
        shortages = {"on": 0, "sp": 0}
        for p in pending:
            dep = self.state.deployments.get(p.deployment)
            if not dep:
                continue
            # compute current spot fraction for this deployment
            running_pods = [rp for rp in self.state.pods.values() if rp.deployment == dep.name and rp.phase == "Running"]
            sp_running = sum(1 for rp in running_pods if (self.state.nodes.get(rp.node_id) and self.state.nodes[rp.node_id].pool == self.config.spot_pool_name))
            on_running = sum(1 for rp in running_pods if (self.state.nodes.get(rp.node_id) and self.state.nodes[rp.node_id].pool == self.config.on_demand_pool_name))
            total_running = max(1, sp_running + on_running)  # avoid div by zero -> treat as 1 for initial schedule
            current_spot_fraction = sp_running / total_running

            def try_bind(pool_name: str) -> bool:
                # find a node with free gpu in pool
                for node in self.state.nodes.values():
                    if node.pool == pool_name and node.free_gpus() > 0:
                        node.used_gpus += 1
                        p.node_id = node.id
                        p.phase = "Running"
                        return True
                return False

            placed = False
            # Try respect preference and cap
            if dep.prefer_spot:
                if current_spot_fraction < dep.spot_fraction_cap:
                    placed = try_bind(self.config.spot_pool_name)
                    if not placed:
                        shortages["sp"] += 1
                if not placed:
                    placed = try_bind(self.config.on_demand_pool_name)
                    if not placed:
                        shortages["on"] += 1
            else:
                placed = try_bind(self.config.on_demand_pool_name)
                if not placed:
                    shortages["on"] += 1
                if not placed and current_spot_fraction < dep.spot_fraction_cap:
                    placed = try_bind(self.config.spot_pool_name)
                    if not placed:
                        shortages["sp"] += 1
        # Provision required nodes for shortages
        if shortages["on"] > 0 or shortages["sp"] > 0:
            self.pool_manager.ensure_capacity(demand_on_demand_gpus=shortages["on"], demand_spot_gpus=shortages["sp"])

    def reconcile(self):
        # 1) For each deployment compute desired replicas
        now = time.time()
        for dep in self.state.deployments.values():
            desired = self._desired_replicas(dep)
            dep.desired_replicas = desired
            running, pending, preempted = self._current_replicas(dep)
            total = running + pending
            if total < desired:
                to_add = min(desired - total, self.config.max_scale_step)
                self._spawn_pods(dep, to_add)
                dep.last_scale_time = now
            elif total > desired:
                # Apply cooldown for scale down
                if (now - dep.last_scale_time) >= self.config.scale_down_cooldown_seconds:
                    to_remove = min(total - desired, self.config.max_scale_step)
                    self._terminate_excess_pods(dep, to_remove)
                    dep.last_scale_time = now
        # 2) Schedule pending pods onto nodes
        self._schedule_pending()
        # 3) Try to reschedule preempted pods
        if self.config.reschedule_on_preemption:
            for p in list(self.state.pods.values()):
                if p.phase == "Preempted":
                    p.phase = "Pending"
                    p.node_id = None
        # 4) Attempt to schedule again after rescheduling
        self._schedule_pending()
        # 5) Clean up idle nodes
        self.pool_manager.scale_down_idle_nodes()

