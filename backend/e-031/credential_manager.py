import os
import secrets
import string
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.exc import IntegrityError
from flask import current_app
from models import db, MachineCredential, CredentialVersion
from utils import encrypt_secret, decrypt_secret, audit_event, generate_access_key


class CredentialError(Exception):
    pass


class CredentialManager:
    def __init__(self, app=None):
        self.app = app or current_app

    def _ensure_interval(self, interval: Optional[int]) -> int:
        cfg = self.app.config
        if interval is None:
            return cfg['DEFAULT_ROTATION_INTERVAL_SECONDS']
        interval = int(interval)
        if interval < cfg['MIN_ROTATION_INTERVAL_SECONDS']:
            raise CredentialError(f"Rotation interval must be >= {cfg['MIN_ROTATION_INTERVAL_SECONDS']} seconds")
        return interval

    def _generate_secret(self, length: int = 48) -> str:
        # urlsafe to ease transport; cryptographically strong
        return secrets.token_urlsafe(length)

    def create_credential(self, name: str, rotation_interval_seconds: Optional[int] = None) -> Tuple[MachineCredential, str]:
        interval = self._ensure_interval(rotation_interval_seconds)
        access_key = generate_access_key(prefix='mch_')
        plaintext_secret = self._generate_secret()
        encrypted_secret = encrypt_secret(plaintext_secret)

        cred = MachineCredential(
            name=name,
            access_key=access_key,
            status='active',
            rotation_interval_seconds=interval,
            last_rotated_at=datetime.utcnow(),
        )
        db.session.add(cred)
        db.session.flush()  # get cred.id

        version = CredentialVersion(
            machine_credential_id=cred.id,
            version=1,
            secret_encrypted=encrypted_secret,
            reason='initial-issue',
        )
        db.session.add(version)
        db.session.flush()

        cred.active_version_id = version.id
        db.session.commit()

        audit_event('credential.created', f"Created credential {cred.id} ({cred.name}) with rotation {interval}s", credential_id=cred.id, version_id=version.id)
        return cred, plaintext_secret

    def get_credential(self, credential_id: str) -> MachineCredential:
        cred = MachineCredential.query.filter_by(id=credential_id).first()
        if not cred:
            raise CredentialError('Credential not found')
        return cred

    def rotate_credential(self, credential_id: str, reason: str = 'manual-rotation') -> Tuple[MachineCredential, str]:
        cred = self.get_credential(credential_id)
        if cred.status != 'active':
            raise CredentialError('Credential is not active')

        # Determine next version number
        next_version_num = 1
        if cred.versions:
            next_version_num = max(v.version for v in cred.versions) + 1

        plaintext_secret = self._generate_secret()
        encrypted_secret = encrypt_secret(plaintext_secret)

        # Revoke previous active version logically by setting revoked_at
        if cred.active_version_id:
            prev = CredentialVersion.query.filter_by(id=cred.active_version_id).first()
            if prev and not prev.revoked_at:
                prev.revoked_at = datetime.utcnow()
                prev.reason = f"revoked-due-to-{reason}"
                db.session.add(prev)

        new_version = CredentialVersion(
            machine_credential_id=cred.id,
            version=next_version_num,
            secret_encrypted=encrypted_secret,
            reason=reason,
        )
        db.session.add(new_version)
        db.session.flush()

        cred.active_version_id = new_version.id
        cred.last_rotated_at = datetime.utcnow()
        db.session.add(cred)
        db.session.commit()

        audit_event('credential.rotated', f"Rotated credential {cred.id}, new version {next_version_num}", credential_id=cred.id, version_id=new_version.id)
        return cred, plaintext_secret

    def revoke_current_version(self, credential_id: str, reason: str = 'manual-revoke', disable: bool = False) -> MachineCredential:
        cred = self.get_credential(credential_id)
        if cred.active_version_id:
            ver = CredentialVersion.query.filter_by(id=cred.active_version_id).first()
            if ver and not ver.revoked_at:
                ver.revoked_at = datetime.utcnow()
                ver.reason = reason
                db.session.add(ver)
        if disable:
            cred.status = 'disabled'
        db.session.add(cred)
        db.session.commit()
        audit_event('credential.revoked', f"Revoked current version for credential {cred.id}. disable={disable}", credential_id=cred.id, version_id=cred.active_version_id)
        return cred

    def breach_detected(self, credential_id: str, reason: str = 'breach-detected') -> Tuple[MachineCredential, str]:
        cred = self.get_credential(credential_id)
        cred.compromised_at = datetime.utcnow()
        db.session.add(cred)
        db.session.commit()
        # revoke current and rotate immediately
        self.revoke_current_version(credential_id, reason=reason, disable=False)
        rotated_cred, new_secret = self.rotate_credential(credential_id, reason='auto-rotation-after-breach')
        audit_event('credential.breach', f"Breach detected for credential {credential_id}; rotated immediately", credential_id=credential_id, version_id=rotated_cred.active_version_id)
        return rotated_cred, new_secret

    def validate(self, access_key: str, plaintext_secret: str) -> Tuple[bool, Optional[str], Optional[str]]:
        cred = MachineCredential.query.filter_by(access_key=access_key).first()
        if not cred:
            return False, None, 'not_found'
        if cred.status != 'active':
            return False, cred.id, cred.status
        if not cred.active_version_id:
            return False, cred.id, 'no_active_version'
        ver = CredentialVersion.query.filter_by(id=cred.active_version_id).first()
        if not ver or ver.revoked_at is not None:
            return False, cred.id, 'revoked'
        try:
            stored_secret = decrypt_secret(ver.secret_encrypted)
        except Exception:
            return False, cred.id, 'decrypt_error'
        if secrets.compare_digest(stored_secret, plaintext_secret):
            return True, cred.id, 'active'
        return False, cred.id, 'invalid_secret'

    def credentials_due_for_rotation(self):
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        creds = MachineCredential.query.filter_by(status='active').all()
        due = []
        for c in creds:
            if c.rotation_interval_seconds <= 0:
                continue
            if c.last_rotated_at is None:
                due.append(c)
            else:
                delta = (now - c.last_rotated_at).total_seconds()
                if delta >= c.rotation_interval_seconds:
                    due.append(c)
        return due

