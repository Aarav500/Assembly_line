from prometheus_client import CollectorRegistry, Gauge, generate_latest
from .config import Config
from .state import ClusterState

_registry = CollectorRegistry()

nodes_total = Gauge('nodes_total', 'Total nodes', ['pool'], registry=_registry)
node_gpus_free = Gauge('node_gpus_free', 'Free GPUs by pool', ['pool'], registry=_registry)
pods_total = Gauge('pods_total', 'Total pods', ['phase'], registry=_registry)
replicas_desired = Gauge('replicas_desired', 'Desired replicas', ['deployment'], registry=_registry)
replicas_running = Gauge('replicas_running', 'Running replicas', ['deployment'], registry=_registry)
replicas_pending = Gauge('replicas_pending', 'Pending replicas', ['deployment'], registry=_registry)
observed_rps = Gauge('observed_rps', 'Observed RPS', ['deployment'], registry=_registry)


def update_metrics(state: ClusterState):
    # reset by setting to zero first? Prometheus client allows overwrite by setting new values
    # pools
    on_nodes = len([n for n in state.nodes.values() if n.pool == 'on-demand'])
    sp_nodes = len([n for n in state.nodes.values() if n.pool == 'spot'])
    nodes_total.labels(pool='on-demand').set(on_nodes)
    nodes_total.labels(pool='spot').set(sp_nodes)

    on_free = state.free_gpus_by_pool('on-demand')
    sp_free = state.free_gpus_by_pool('spot')
    node_gpus_free.labels(pool='on-demand').set(on_free)
    node_gpus_free.labels(pool='spot').set(sp_free)

    # pods
    total_pending = len([p for p in state.pods.values() if p.phase == 'Pending'])
    total_running = len([p for p in state.pods.values() if p.phase == 'Running'])
    total_preempted = len([p for p in state.pods.values() if p.phase == 'Preempted'])
    pods_total.labels(phase='Pending').set(total_pending)
    pods_total.labels(phase='Running').set(total_running)
    pods_total.labels(phase='Preempted').set(total_preempted)

    for d in state.deployments.values():
        replicas_desired.labels(deployment=d.name).set(d.desired_replicas)
        running = len(state.running_pods_for_deployment(d.name))
        pending = len([p for p in state.pods_for_deployment(d.name) if p.phase == 'Pending'])
        replicas_running.labels(deployment=d.name).set(running)
        replicas_pending.labels(deployment=d.name).set(pending)
        observed_rps.labels(deployment=d.name).set(d.observed_rps)


def metrics_wsgi_app():
    return generate_latest(_registry)

