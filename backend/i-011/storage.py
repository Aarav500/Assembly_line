import threading
from typing import Dict, List, Optional, Tuple
from models import Secret, Lease
from utils import uuid_str, now_ts

class Storage:
    def __init__(self):
        self._lock = threading.RLock()
        self.secrets: Dict[str, Secret] = {}
        self.leases: Dict[str, Lease] = {}
        self._leases_by_secret: Dict[str, List[str]] = {}

    # Secret management
    def create_secret(self, name: str, value: str, ttl: int, max_ttl: int) -> Tuple[Secret, Lease]:
        with self._lock:
            sid = uuid_str()
            secret = Secret(id=sid, name=name, created_at=now_ts(), updated_at=now_ts())
            secret.latest_version = 1
            secret.versions[1] = value
            self.secrets[sid] = secret
            lease = self._create_lease_unlocked(sid, 1, ttl, max_ttl)
            return secret, lease

    def get_secret(self, secret_id: str) -> Optional[Secret]:
        with self._lock:
            return self.secrets.get(secret_id)

    def rotate_secret(self, secret_id: str, value: str, ttl: Optional[int], max_ttl: Optional[int], revoke_old_after_seconds: int) -> Tuple[Secret, Lease]:
        with self._lock:
            secret = self.secrets.get(secret_id)
            if not secret:
                raise KeyError('secret not found')
            old_version = secret.latest_version
            new_version = old_version + 1
            secret.versions[new_version] = value
            secret.latest_version = new_version
            secret.updated_at = now_ts()

            # Choose ttl/max_ttl for new lease
            sel_ttl = ttl if ttl is not None else 3600
            sel_max_ttl = max_ttl if max_ttl is not None else 86400
            if sel_ttl <= 0 or sel_max_ttl <= 0 or sel_ttl > sel_max_ttl:
                raise ValueError('invalid ttl/max_ttl')

            lease = self._create_lease_unlocked(secret_id, new_version, sel_ttl, sel_max_ttl)

            # Schedule revocation of all old leases after grace period
            if revoke_old_after_seconds <= 0:
                self._revoke_all_leases_unlocked(secret_id, version=old_version)
            else:
                now = now_ts()
                for lid in self._leases_by_secret.get(secret_id, []):
                    l = self.leases[lid]
                    if l.version == old_version and not l.revoked_at:
                        l.planned_revocation_at = now + revoke_old_after_seconds

            return secret, lease

    def delete_secret(self, secret_id: str):
        with self._lock:
            if secret_id not in self.secrets:
                raise KeyError('not found')
            # revoke all leases
            self._revoke_all_leases_unlocked(secret_id, version=None)
            # remove leases index
            for lid in self._leases_by_secret.get(secret_id, [])[:]:
                self.leases.pop(lid, None)
            self._leases_by_secret.pop(secret_id, None)
            # remove secret
            self.secrets.pop(secret_id, None)

    # Lease management
    def _create_lease_unlocked(self, secret_id: str, version: int, ttl: int, max_ttl: int) -> Lease:
        lease = Lease(id=uuid_str(), secret_id=secret_id, version=version, created_at=now_ts(), ttl=ttl, max_ttl=max_ttl)
        self.leases[lease.id] = lease
        self._leases_by_secret.setdefault(secret_id, []).append(lease.id)
        return lease

    def create_lease(self, secret_id: str, version: Optional[int], ttl: int, max_ttl: int) -> Lease:
        with self._lock:
            secret = self.secrets.get(secret_id)
            if not secret:
                raise KeyError('secret not found')
            if version is None:
                version = secret.latest_version
            elif version not in secret.versions:
                raise KeyError('version not found')
            return self._create_lease_unlocked(secret_id, version, ttl, max_ttl)

    def get_lease(self, lease_id: str) -> Optional[Lease]:
        with self._lock:
            return self.leases.get(lease_id)

    def renew_lease(self, lease_id: str, additional_ttl: int) -> Lease:
        with self._lock:
            lease = self.leases.get(lease_id)
            if not lease:
                raise KeyError('lease not found')
            now = now_ts()
            if lease.revoked_at or lease.is_expired(now):
                raise ValueError('cannot renew expired or revoked lease')
            # Current elapsed lifetime
            elapsed = now - lease.created_at
            new_effective = elapsed + additional_ttl
            if new_effective > lease.max_ttl:
                # Cap ttl so that created_at + ttl == created_at + max_ttl
                lease.ttl = int(lease.max_ttl)
            else:
                lease.ttl = int(new_effective)
            return lease

    def revoke_lease(self, lease_id: str) -> Lease:
        with self._lock:
            lease = self.leases.get(lease_id)
            if not lease:
                raise KeyError('lease not found')
            if not lease.revoked_at:
                lease.revoked_at = now_ts()
            return lease

    def revoke_all_leases(self, secret_id: str, version: Optional[int]) -> int:
        with self._lock:
            if secret_id not in self.secrets:
                raise KeyError('secret not found')
            return self._revoke_all_leases_unlocked(secret_id, version)

    def _revoke_all_leases_unlocked(self, secret_id: str, version: Optional[int]) -> int:
        count = 0
        for lid in self._leases_by_secret.get(secret_id, []):
            l = self.leases.get(lid)
            if not l:
                continue
            if version is None or l.version == version:
                if not l.revoked_at:
                    l.revoked_at = now_ts()
                    count += 1
        return count

    def list_leases_by_secret(self, secret_id: str) -> List[Lease]:
        with self._lock:
            ids = self._leases_by_secret.get(secret_id, [])
            return [self.leases[i] for i in ids if i in self.leases]

    # Background maintenance
    def enforce_planned_revocations(self):
        with self._lock:
            now = now_ts()
            for lease in list(self.leases.values()):
                if lease.planned_revocation_at and not lease.revoked_at:
                    if now >= lease.planned_revocation_at:
                        lease.revoked_at = now
                        lease.planned_revocation_at = None

    def cleanup_old_leases(self, retention_seconds: int = 7 * 24 * 3600):
        # Remove leases that are revoked or expired for a long time to keep memory small
        with self._lock:
            now = now_ts()
            to_remove: List[str] = []
            for lid, lease in self.leases.items():
                expired_since = (lease.created_at + lease.ttl)
                if lease.revoked_at and (now - lease.revoked_at) > retention_seconds:
                    to_remove.append(lid)
                elif not lease.revoked_at and expired_since < now and (now - expired_since) > retention_seconds:
                    to_remove.append(lid)
            if to_remove:
                for lid in to_remove:
                    lease = self.leases.pop(lid, None)
                    if lease:
                        arr = self._leases_by_secret.get(lease.secret_id)
                        if arr and lid in arr:
                            arr.remove(lid)
                        if arr is not None and not arr:
                            self._leases_by_secret.pop(lease.secret_id, None)

