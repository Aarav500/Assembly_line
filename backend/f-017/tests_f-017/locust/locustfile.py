import os
import random
from locust import HttpUser, task, between


class ApiUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(1)
    def health(self):
        with self.client.get("/health", name="GET /health", catch_response=True) as res:
            if res.status_code != 200 or res.json().get("status") != "ok":
                res.failure("Health check failed")

    @task(3)
    def items(self):
        count = random.randint(1, 50)
        delay = 50 if random.random() < 0.2 else 0
        name = f"GET /items?count={{count}}&delay_ms=..."  # aggregate
        with self.client.get(f"/items?count={count}&delay_ms={delay}", name=name, catch_response=True) as res:
            if res.status_code != 200:
                res.failure(f"Bad status: {res.status_code}")
                return
            try:
                if res.json().get("count") != count:
                    res.failure("Count mismatch")
            except Exception as e:
                res.failure(f"Invalid JSON: {e}")


# Usage example (headless):
#   locust -f tests/locust/locustfile.py --headless -u 10 -r 2 -t 30s --host http://127.0.0.1:5000 

