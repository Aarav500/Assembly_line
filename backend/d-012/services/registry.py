from typing import Optional
from models import ServiceState
from datetime import datetime


class ServiceRegistry:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get_or_create(self, service: str) -> ServiceState:
        session = self.session_factory()
        try:
            state = session.get(ServiceState, service)
            if not state:
                state = ServiceState(service=service, current_version=None, last_good_version=None)
                session.add(state)
                session.commit()
                session.refresh(state)
            return state
        finally:
            session.close()

    def set_current_version(self, service: str, version: Optional[str]):
        session = self.session_factory()
        try:
            state = session.get(ServiceState, service)
            if not state:
                state = ServiceState(service=service)
                session.add(state)
            state.current_version = version
            state.updated_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

    def mark_good(self, service: str, version: str):
        session = self.session_factory()
        try:
            state = session.get(ServiceState, service)
            if not state:
                state = ServiceState(service=service)
                session.add(state)
            state.current_version = version
            state.last_good_version = version
            state.updated_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

    def rollback(self, service: str, to_version: Optional[str]):
        session = self.session_factory()
        try:
            state = session.get(ServiceState, service)
            if not state:
                raise ValueError(f'Service {service} not found')
            state.current_version = to_version
            state.updated_at = datetime.utcnow()
            session.commit()
        finally:
            session.close()

    def list_states(self):
        session = self.session_factory()
        try:
            return [s.to_dict() for s in session.query(ServiceState).all()]
        finally:
            session.close()

