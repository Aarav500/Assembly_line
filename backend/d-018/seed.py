# Seed the storage with sample runners
import os
import json
from config import STORAGE_FILE, DEFAULT_POLICY

sample = {
    "policy": DEFAULT_POLICY,
    "runners": [
        {
            "id": "r-aws-spot",
            "name": "aws-spot-large",
            "provider": "aws",
            "cost_per_minute": 0.015,
            "cpu": 8,
            "memory_mb": 32768,
            "performance_score": 1.2,
            "labels": ["linux", "x86_64", "docker"],
            "online": True,
            "capacity": 5,
            "running_jobs": 1,
            "queue_time_estimate": 2.0,
            "preemptible": True,
            "meta": {"instance_type": "m6i.2xlarge"}
        },
        {
            "id": "r-gcp-preemptible",
            "name": "gcp-preemptible-medium",
            "provider": "gcp",
            "cost_per_minute": 0.012,
            "cpu": 4,
            "memory_mb": 16384,
            "performance_score": 1.0,
            "labels": ["linux", "x86_64", "docker"],
            "online": True,
            "capacity": 10,
            "running_jobs": 3,
            "queue_time_estimate": 4.0,
            "preemptible": True,
            "meta": {"machine_type": "n2-standard-4"}
        },
        {
            "id": "r-azure-on-demand",
            "name": "azure-on-demand-fast",
            "provider": "azure",
            "cost_per_minute": 0.035,
            "cpu": 8,
            "memory_mb": 32768,
            "performance_score": 2.0,
            "labels": ["linux", "x86_64", "docker"],
            "online": True,
            "capacity": 3,
            "running_jobs": 0,
            "queue_time_estimate": 1.0,
            "preemptible": False,
            "meta": {"vm_size": "F8s_v2"}
        },
        {
            "id": "r-onprem-gpu",
            "name": "onprem-gpu-a100",
            "provider": "onprem",
            "cost_per_minute": 0.02,
            "cpu": 16,
            "memory_mb": 131072,
            "performance_score": 3.0,
            "labels": ["linux", "x86_64", "gpu", "docker"],
            "online": True,
            "capacity": 2,
            "running_jobs": 1,
            "queue_time_estimate": 6.0,
            "preemptible": False,
            "meta": {"gpu": "A100"}
        }
    ]
}

os.makedirs(os.path.dirname(STORAGE_FILE), exist_ok=True)
with open(STORAGE_FILE, "w", encoding="utf-8") as f:
    json.dump(sample, f, indent=2)
print(f"Seeded {STORAGE_FILE} with sample data.")

