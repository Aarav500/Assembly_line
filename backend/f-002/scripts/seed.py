import os
import requests

BASE = os.getenv("BASE_URL", "http://localhost:8080")

for name in ["payments", "search", "orders"]:
    r = requests.post(f"{BASE}/api/projects", json={"name": name, "createDashboards": True})
    print(name, r.status_code, r.text)

