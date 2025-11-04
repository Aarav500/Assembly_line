from typing import List, Optional, Dict, Any
from sqlalchemy import select
from models import db, Organization, Agent, Resource


class OrganizationRepository:
    @staticmethod
    def create(name: str) -> Organization:
        org = Organization(name=name, api_key=Organization.generate_api_key())
        db.session.add(org)
        db.session.commit()
        return org

    @staticmethod
    def get_by_id(org_id: int) -> Optional[Organization]:
        return db.session.get(Organization, org_id)


class AgentRepository:
    @staticmethod
    def create(org: Organization, name: str, type: str, config: Optional[Dict[str, Any]] = None) -> Agent:
        agent = Agent(name=name, type=type, config=config or {}, org_id=org.id)
        db.session.add(agent)
        db.session.commit()
        return agent

    @staticmethod
    def list_for_org(org: Organization) -> List[Agent]:
        return db.session.execute(select(Agent).filter_by(org_id=org.id)).scalars().all()

    @staticmethod
    def get_for_org(org: Organization, agent_id: int) -> Optional[Agent]:
        return db.session.execute(select(Agent).filter_by(id=agent_id, org_id=org.id)).scalar_one_or_none()


class ResourceRepository:
    @staticmethod
    def create(org: Organization, title: str, content: str) -> Resource:
        resource = Resource(title=title, content=content, org_id=org.id)
        db.session.add(resource)
        db.session.commit()
        return resource

    @staticmethod
    def list_for_org(org: Organization) -> List[Resource]:
        return db.session.execute(select(Resource).filter_by(org_id=org.id).order_by(Resource.created_at.desc())).scalars().all()

    @staticmethod
    def get_for_org(org: Organization, resource_id: int) -> Optional[Resource]:
        return db.session.execute(select(Resource).filter_by(id=resource_id, org_id=org.id)).scalar_one_or_none()


