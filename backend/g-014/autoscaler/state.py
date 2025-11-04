import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class Node:
    id: str
    pool: str  # on-demand or spot
    total_gpus: int
    used_gpus: int = 0
    created_at: float = field(default_factory=lambda: time.time())
    preemptible: bool = False
    terminating: bool = False

    def free_gpus(self) -> int:
        return max(0, self.total_gpus - self.used_gpus)

    def to_dict(self):
        return {
            "id": self.id,
            "pool": self.pool,
            "total_gpus": self.total_gpus,
            "used_gpus": self.used_gpus,
            "created_at": self.created_at,
            "preemptible": self.preemptible,
            "terminating": self.terminating,
        }


@dataclass
class Pod:
    id: str
    deployment: str
    node_id: Optional[str] = None
    phase: str = "Pending"  # Pending/Running/Preempted/Terminating
    created_at: float = field(default_factory=lambda: time.time())

    def to_dict(self):
        return {
            "id": self.id,
            "deployment": self.deployment,
            "node_id": self.node_id,
            "phase": self.phase,
            "created_at": self.created_at,
        }


@dataclass
class Deployment:
    name: str
    target_rps_per_replica: float
    min_replicas: int = 0
    max_replicas: int = 1000
    prefer_spot: bool = True
    spot_fraction_cap: float = 0.8
    desired_replicas: int = 0
    observed_rps: float = 0.0
    last_scale_time: float = field(default_factory=lambda: time.time())

    def to_dict(self, pods: List[Pod]):
        running = [p for p in pods if p.deployment == self.name and p.phase == "Running"]
        pending = [p for p in pods if p.deployment == self.name and p.phase == "Pending"]
        preempted = [p for p in pods if p.deployment == self.name and p.phase == "Preempted"]
        return {
            "name": self.name,
            "target_rps_per_replica": self.target_rps_per_replica,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "prefer_spot": self.prefer_spot,
            "spot_fraction_cap": self.spot_fraction_cap,
            "desired_replicas": self.desired_replicas,
            "observed_rps": self.observed_rps,
            "replicas": {
                "running": len(running),
                "pending": len(pending),
                "preempted": len(preempted),
            },
        }


@dataclass
class ClusterState:
    nodes: Dict[str, Node] = field(default_factory=dict)
    pods: Dict[str, Pod] = field(default_factory=dict)
    deployments: Dict[str, Deployment] = field(default_factory=dict)

    def add_node(self, pool: str, total_gpus: int, preemptible: bool) -> Node:
        node = Node(id=str(uuid.uuid4()), pool=pool, total_gpus=total_gpus, preemptible=preemptible)
        self.nodes[node.id] = node
        return node

    def remove_node(self, node_id: str):
        node = self.nodes.get(node_id)
        if not node:
            return
        # Evict pods
        for p in list(self.pods.values()):
            if p.node_id == node_id and p.phase in ("Running", "Pending"):
                p.node_id = None
                p.phase = "Preempted"
        node.terminating = True
        del self.nodes[node_id]

    def add_pod(self, deployment: str) -> Pod:
        pod = Pod(id=str(uuid.uuid4()), deployment=deployment, phase="Pending")
        self.pods[pod.id] = pod
        return pod

    def remove_pod(self, pod_id: str):
        if pod_id in self.pods:
            del self.pods[pod_id]

    def add_deployment(self, name: str, target_rps_per_replica: float, min_replicas: int, max_replicas: int, prefer_spot: bool, spot_fraction_cap: float):
        self.deployments[name] = Deployment(
            name=name,
            target_rps_per_replica=target_rps_per_replica,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            prefer_spot=prefer_spot,
            spot_fraction_cap=spot_fraction_cap,
        )

    def remove_deployment(self, name: str):
        # Remove pods
        for pid, p in list(self.pods.items()):
            if p.deployment == name:
                del self.pods[pid]
        # Remove deployment
        if name in self.deployments:
            del self.deployments[name]

    def to_dict(self):
        nodes = [n.to_dict() for n in self.nodes.values()]
        pods = [p.to_dict() for p in self.pods.values()]
        deployments = [d.to_dict(pods=self.pods_for_deployment(d.name)) for d in self.deployments.values()]
        return {
            "nodes": nodes,
            "pods": pods,
            "deployments": deployments,
        }

    def pods_for_deployment(self, name: str) -> List[Pod]:
        return [p for p in self.pods.values() if p.deployment == name]

    def running_pods_for_deployment(self, name: str) -> List[Pod]:
        return [p for p in self.pods.values() if p.deployment == name and p.phase == "Running"]

    def pending_pods(self) -> List[Pod]:
        return [p for p in self.pods.values() if p.phase == "Pending"]

    def free_gpus_by_pool(self, pool: str) -> int:
        return sum(n.free_gpus() for n in self.nodes.values() if n.pool == pool)

    def total_gpus_by_pool(self, pool: str) -> int:
        return sum(n.total_gpus for n in self.nodes.values() if n.pool == pool)

    def total_running_pods_in_pool(self, pool: str) -> int:
        node_ids = {n.id for n in self.nodes.values() if n.pool == pool}
        return sum(1 for p in self.pods.values() if p.phase == "Running" and p.node_id in node_ids)

