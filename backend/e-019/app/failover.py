from typing import Any, Dict, Tuple
import time

from .config import Config
from . import state_manager
from .healthcheck import is_url_healthy
from .dns_providers.base import DNSProvider
from .dns_providers.mock import MockDNSProvider
from .dns_providers.route53 import Route53Provider
from .dns_providers.cloudflare import CloudflareProvider


def _build_dns_provider(cfg: Config) -> DNSProvider | None:
    p = cfg.dns_provider.lower()
    if p == "none":
        return None
    if p == "mock":
        return MockDNSProvider()
    if p == "route53":
        if not cfg.route53_hosted_zone_id:
            raise ValueError("ROUTE53_HOSTED_ZONE_ID must be set for route53 provider")
        return Route53Provider(cfg.route53_hosted_zone_id, cfg.aws_region)
    if p == "cloudflare":
        if not cfg.cloudflare_api_token or not cfg.cloudflare_zone_id:
            raise ValueError("CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID must be set for cloudflare provider")
        return CloudflareProvider(cfg.cloudflare_api_token, cfg.cloudflare_zone_id)
    raise ValueError(f"Unsupported DNS provider: {cfg.dns_provider}")


class FailoverManager:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.provider = _build_dns_provider(cfg)

    def _region_key(self, region: str) -> str:
        return "primary" if region == self.cfg.primary_region else "secondary"

    def current_state(self) -> Dict[str, Any]:
        return state_manager.load_state(self.cfg.state_file)

    def _check_health(self, region: str, state: Dict[str, Any]) -> bool:
        key = self._region_key(region)
        if state.get("simulated_outage", {}).get(key, False):
            return False
        url = self.cfg.primary_health_url if key == "primary" else self.cfg.secondary_health_url
        return is_url_healthy(url, timeout=self.cfg.health_timeout, retries=self.cfg.health_retries)

    def evaluate(self) -> Dict[str, Any]:
        state = self.current_state()
        # set default active region if not set
        if not state.get("active_region"):
            state = state_manager.set_active_region(self.cfg.state_file, self.cfg.primary_region, reason="initial")
        active = state["active_region"]
        primary_ok = self._check_health(self.cfg.primary_region, state)
        secondary_ok = self._check_health(self.cfg.secondary_region, state)
        return {
            "active_region": active,
            "primary_ok": primary_ok,
            "secondary_ok": secondary_ok,
            "state": state,
        }

    def _update_dns(self, region: str) -> Dict[str, Any] | None:
        if not self.provider:
            return None
        value = self.cfg.record_value_for_region(region)
        return self.provider.update_record(self.cfg.dns_record_name, self.cfg.dns_record_type, value, self.cfg.dns_ttl)

    def sync_dns(self) -> Dict[str, Any]:
        state = self.current_state()
        region = state.get("active_region") or self.cfg.primary_region
        resp = self._update_dns(region)
        state_manager.set_dns_sync(self.cfg.state_file)
        return {"synced_to": region, "dns_response": resp}

    def set_active(self, region: str, reason: str) -> Dict[str, Any]:
        if region not in (self.cfg.primary_region, self.cfg.secondary_region):
            raise ValueError("Invalid region")
        # update DNS first
        dns_resp = self._update_dns(region)
        state = state_manager.set_active_region(self.cfg.state_file, region, reason)
        state_manager.set_dns_sync(self.cfg.state_file)
        return {"active_region": region, "dns_response": dns_resp, "state": state}

    def failover(self) -> Dict[str, Any]:
        # set active to the other region
        state = self.current_state()
        current = state.get("active_region") or self.cfg.primary_region
        target = self.cfg.other_region(current)
        return self.set_active(target, reason="manual-failover")

    def failback(self) -> Dict[str, Any]:
        return self.set_active(self.cfg.primary_region, reason="manual-failback")

    def evaluate_and_act(self) -> Dict[str, Any]:
        evaluation = self.evaluate()
        active = evaluation["active_region"]
        primary_ok = evaluation["primary_ok"]
        secondary_ok = evaluation["secondary_ok"]
        decision = {
            "action": "none",
            "from": active,
            "to": None,
            "reason": None,
        }
        if active == self.cfg.primary_region:
            if not primary_ok and secondary_ok:
                # fail over to secondary
                decision.update({"action": "failover", "to": self.cfg.secondary_region, "reason": "primary-unhealthy"})
                result = self.set_active(self.cfg.secondary_region, reason=decision["reason"]) 
                decision["result"] = result
            else:
                decision["result"] = {"status": "no-change"}
        else:
            # active is secondary
            if not secondary_ok and primary_ok:
                decision.update({"action": "failover", "to": self.cfg.primary_region, "reason": "secondary-unhealthy"})
                result = self.set_active(self.cfg.primary_region, reason=decision["reason"]) 
                decision["result"] = result
            elif self.cfg.auto_failback and primary_ok:
                decision.update({"action": "failback", "to": self.cfg.primary_region, "reason": "auto-failback-primary-healthy"})
                result = self.set_active(self.cfg.primary_region, reason=decision["reason"]) 
                decision["result"] = result
            else:
                decision["result"] = {"status": "no-change"}
        evaluation["decision"] = decision
        return evaluation

