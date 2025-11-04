from typing import Dict, Any
import yaml


def generate_hpa_yaml(name: str, namespace: str, target: Dict[str, Any], min_replicas: int, max_replicas: int, cpu_target_utilization: int) -> str:
    api_version = target.get("apiVersion", "apps/v1")
    kind = target.get("kind", "Deployment")
    ref_name = target.get("name")
    if not ref_name:
        raise ValueError("target.name is required for HPA")

    doc = {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "scaleTargetRef": {
                "apiVersion": api_version,
                "kind": kind,
                "name": ref_name,
            },
            "minReplicas": int(min_replicas),
            "maxReplicas": int(max_replicas),
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": int(cpu_target_utilization),
                        },
                    },
                }
            ],
        },
    }
    return yaml.safe_dump(doc, sort_keys=False)


def generate_vpa_yaml(name: str, namespace: str, target: Dict[str, Any], container_name: str, min_allowed: Dict[str, Any], max_allowed: Dict[str, Any], update_mode: str = "Auto") -> str:
    api_version = target.get("apiVersion", "apps/v1")
    kind = target.get("kind", "Deployment")
    ref_name = target.get("name")
    if not ref_name:
        raise ValueError("target.name is required for VPA")

    # Clean None fields
    def drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    container_policy = {
        "containerName": container_name,
        "minAllowed": drop_none({
            "cpu": min_allowed.get("cpu"),
            "memory": min_allowed.get("memory"),
        }),
        "maxAllowed": drop_none({
            "cpu": max_allowed.get("cpu"),
            "memory": max_allowed.get("memory"),
        }),
    }

    doc = {
        "apiVersion": "autoscaling.k8s.io/v1",
        "kind": "VerticalPodAutoscaler",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "targetRef": {"apiVersion": api_version, "kind": kind, "name": ref_name},
            "updatePolicy": {"updateMode": update_mode},
            "resourcePolicy": {"containerPolicies": [container_policy]},
        },
    }
    return yaml.safe_dump(doc, sort_keys=False)

