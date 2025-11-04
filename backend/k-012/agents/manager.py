from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from flask import jsonify
from models import Organization, Agent
from repositories import AgentRepository, ResourceRepository
from tenant import TenantContext


class AgentBase:
    def __init__(self, agent: Agent):
        self.agent = agent

    def run_action(self, action: str, payload: Dict[str, Any], tenant: TenantContext) -> Dict[str, Any]:
        raise NotImplementedError


class EchoAgent(AgentBase):
    def run_action(self, action: str, payload: Dict[str, Any], tenant: TenantContext) -> Dict[str, Any]:
        if action == 'list_resources':
            cached = tenant.cache_get('agents:echo:list_resources')
            if cached is not None:
                return {"cached": True, "resources": cached}
            items = ResourceRepository.list_for_org(tenant.org)
            data = [{"id": r.id, "title": r.title} for r in items]
            tenant.cache_set('agents:echo:list_resources', data, ttl_seconds=10)
            return {"cached": False, "resources": data}
        elif action == 'summarize':
            # naive token-free summarization: count total chars and items
            items = ResourceRepository.list_for_org(tenant.org)
            total_chars = sum(len(r.content) for r in items)
            return {
                "summary": {
                    "resource_count": len(items),
                    "total_characters": total_chars,
                }
            }
        else:
            return {"error": {"code": "unknown_action", "message": f"Unknown action: {action}"}}


AGENT_TYPES = {
    'echo': EchoAgent,
}


@dataclass
class AgentManager:
    org: Organization

    def load(self, agent_id: int) -> Optional[Agent]:
        return AgentRepository.get_for_org(self.org, agent_id)

    def run(self, agent_id: int, action: str, payload: Dict[str, Any], tenant: TenantContext) -> Dict[str, Any]:
        agent = self.load(agent_id)
        if not agent:
            return {"error": {"code": "not_found", "message": "Agent not found in this organization"}}
        impl_cls = AGENT_TYPES.get(agent.type)
        if not impl_cls:
            return {"error": {"code": "unsupported_agent", "message": f"Unsupported agent type: {agent.type}"}}
        impl = impl_cls(agent)
        return impl.run_action(action, payload, tenant)


