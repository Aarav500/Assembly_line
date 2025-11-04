from typing import List, Dict
from .base import BaseProvider
from services.cost_models import price_for


class MockProvider(BaseProvider):
    name = "mock"

    def list_resources(self) -> List[Dict]:
        # Deterministic sample resources and metrics
        resources = [
            {
                "id": "i-mock-001",
                "name": "mock-api-prod-1",
                "provider": "aws",
                "resource_type": "vm",
                "region": "us-east-1",
                "instance_type": "m5.large",
                "instance_family": "m5",
                "vcpus": 2,
                "memory_gb": 8,
                "cost_per_hour": price_for("m5.large", "us-east-1"),
                "tags": {"env": "prod", "team": "api"},
                "metrics": {
                    "avg_cpu": 0.10,
                    "peak_cpu": 0.30,
                    "avg_mem": 0.22,
                    "peak_mem": 0.45,
                    "avg_network_io_mbps": 3.2,
                    "idle_hours_7d": 48,
                },
            },
            {
                "id": "i-mock-002",
                "name": "mock-worker-dev-1",
                "provider": "aws",
                "resource_type": "vm",
                "region": "us-west-2",
                "instance_type": "t3.medium",
                "instance_family": "t3",
                "vcpus": 2,
                "memory_gb": 4,
                "cost_per_hour": price_for("t3.medium", "us-west-2"),
                "tags": {"env": "dev", "team": "worker"},
                "metrics": {
                    "avg_cpu": 0.03,
                    "peak_cpu": 0.10,
                    "avg_mem": 0.10,
                    "peak_mem": 0.20,
                    "avg_network_io_mbps": 0.4,
                    "idle_hours_7d": 180,
                },
            },
            {
                "id": "i-mock-003",
                "name": "mock-db-prod-1",
                "provider": "aws",
                "resource_type": "vm",
                "region": "eu-central-1",
                "instance_type": "m5.xlarge",
                "instance_family": "m5",
                "vcpus": 4,
                "memory_gb": 16,
                "cost_per_hour": price_for("m5.xlarge", "eu-central-1"),
                "tags": {"env": "prod", "team": "db"},
                "metrics": {
                    "avg_cpu": 0.90,
                    "peak_cpu": 0.99,
                    "avg_mem": 0.75,
                    "peak_mem": 0.94,
                    "avg_network_io_mbps": 12.4,
                    "idle_hours_7d": 5,
                },
            },
            {
                "id": "i-mock-004",
                "name": "mock-cache-stage-1",
                "provider": "aws",
                "resource_type": "vm",
                "region": "us-east-2",
                "instance_type": "c5.large",
                "instance_family": "c5",
                "vcpus": 2,
                "memory_gb": 4,
                "cost_per_hour": price_for("c5.large", "us-east-2"),
                "tags": {"env": "stage", "team": "platform"},
                "metrics": {
                    "avg_cpu": 0.50,
                    "peak_cpu": 0.70,
                    "avg_mem": 0.35,
                    "peak_mem": 0.60,
                    "avg_network_io_mbps": 8.0,
                    "idle_hours_7d": 24,
                },
            },
        ]
        return resources

