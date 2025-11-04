import random
import time
from typing import Tuple

from .config import Config
from .state import ClusterState


class GPUPoolManager:
    def __init__(self, config: Config, state: ClusterState):
        self.config = config
        self.state = state
        self._last_eviction_check = time.time()

    def desired_nodes_for_gpus(self, desired_gpus: int) -> int:
        per = max(1, self.config.gpu_per_node)
        return (desired_gpus + per - 1) // per

    def ensure_capacity(self, demand_on_demand_gpus: int, demand_spot_gpus: int) -> Tuple[int, int]:
        # Returns tuple of nodes added (on-demand, spot)
        added_on_demand = 0
        added_spot = 0
        # On-demand
        free_on_demand = self.state.free_gpus_by_pool(self.config.on_demand_pool_name)
        deficit_on_demand = max(0, demand_on_demand_gpus - free_on_demand)
        if deficit_on_demand > 0:
            need_nodes = self.desired_nodes_for_gpus(deficit_on_demand)
            for _ in range(need_nodes):
                self.state.add_node(pool=self.config.on_demand_pool_name, total_gpus=self.config.gpu_per_node, preemptible=False)
                added_on_demand += 1
        # Spot
        free_spot = self.state.free_gpus_by_pool(self.config.spot_pool_name)
        deficit_spot = max(0, demand_spot_gpus - free_spot)
        if deficit_spot > 0:
            need_nodes = self.desired_nodes_for_gpus(deficit_spot)
            for _ in range(need_nodes):
                self.state.add_node(pool=self.config.spot_pool_name, total_gpus=self.config.gpu_per_node, preemptible=True)
                added_spot += 1
        return added_on_demand, added_spot

    def scale_down_idle_nodes(self):
        # Remove nodes that are idle and older than startup + cooldown
        now = time.time()
        for node_id, node in list(self.state.nodes.items()):
            if node.used_gpus == 0 and (now - node.created_at) > (self.config.node_startup_seconds + self.config.scale_down_cooldown_seconds):
                self.state.remove_node(node_id)

    def tick(self):
        # random spot evictions according to rate per minute
        now = time.time()
        elapsed = max(0.001, now - self._last_eviction_check)
        self._last_eviction_check = now
        rate_per_sec = float(self.config.global_spot_eviction_rate_per_minute) / 60.0
        p = 1.0 - pow(1.0 - rate_per_sec, elapsed)  # convert to per-interval probability
        for node in list(self.state.nodes.values()):
            if node.preemptible and not node.terminating:
                if random.random() < p:
                    # Evict node
                    self.state.remove_node(node.id)
        # attempt to scale down idle nodes
        self.scale_down_idle_nodes()

