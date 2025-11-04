import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from models import IncidentTicket


class IncidentManager:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create_incident(self,
                        service: str,
                        attempted_version: str,
                        previous_version: Optional[str],
                        rollback_version: Optional[str],
                        snapshot: Dict[str, Any]) -> int:
        session = self.session_factory()
        try:
            ticket = IncidentTicket(
                service=service,
                attempted_version=attempted_version,
                previous_version=previous_version,
                rollback_version=rollback_version,
                status='open',
                snapshot=json.dumps(snapshot)
            )
            session.add(ticket)
            session.commit()
            session.refresh(ticket)
            return ticket.id
        finally:
            session.close()

    def resolve_incident(self, incident_id: int) -> bool:
        session = self.session_factory()
        try:
            ticket = session.get(IncidentTicket, incident_id)
            if not ticket:
                return False
            ticket.status = 'resolved'
            ticket.resolved_at = datetime.utcnow()
            session.commit()
            return True
        finally:
            session.close()

    def get_incident(self, incident_id: int) -> Optional[Dict[str, Any]]:
        session = self.session_factory()
        try:
            ticket = session.get(IncidentTicket, incident_id)
            return ticket.to_dict() if ticket else None
        finally:
            session.close()

    def list_incidents(self) -> List[Dict[str, Any]]:
        session = self.session_factory()
        try:
            tickets = session.query(IncidentTicket).order_by(IncidentTicket.created_at.desc()).all()
            return [t.to_dict() for t in tickets]
        finally:
            session.close()

