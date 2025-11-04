import asyncio
import httpx
from typing import Any, Dict, List, Optional


class PrometheusClient:
    def __init__(self, base_url: str, verify: bool = True, timeout_seconds: int = 15):
        self.base_url = base_url.rstrip("/")
        self.verify = verify
        self.timeout = httpx.Timeout(timeout_seconds)
        self._client = httpx.AsyncClient(verify=verify, timeout=self.timeout)

    async def close(self):
        await self._client.aclose()

    async def query(self, expr: str, time: Optional[float] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"query": expr}
        if time is not None:
            params["time"] = time
        r = await self._client.get(f"{self.base_url}/api/v1/query", params=params)
        r.raise_for_status()
        return r.json()

    async def query_range(self, expr: str, start: float, end: float, step: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "query": expr,
            "start": start,
            "end": end,
            "step": step,
        }
        r = await self._client.get(f"{self.base_url}/api/v1/query_range", params=params)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def extract_vector(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        if result.get("status") != "success":
            return []
        data = result.get("data", {})
        if data.get("resultType") != "vector":
            return []
        return data.get("result", [])

    @staticmethod
    def extract_matrix(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        if result.get("status") != "success":
            return []
        data = result.get("data", {})
        if data.get("resultType") != "matrix":
            return []
        return data.get("result", [])

