from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Repository(Base):
    __tablename__ = "repositories"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(255), unique=True, index=True, nullable=False)


class PullRequest(Base):
    __tablename__ = "pull_requests"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    number = Column(Integer, index=True, nullable=False)
    head_sha = Column(String(64), index=True)
    status = Column(String(32), default="pending")  # pending, pass, fail
    last_evaluated_at = Column(DateTime)

    repo = relationship("Repository")


class Commit(Base):
    __tablename__ = "commits"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, index=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=True, index=True)

    sha = Column(String(64), index=True, nullable=False)
    author_name = Column(String(255))
    author_email = Column(String(255))
    committer_name = Column(String(255))
    committer_email = Column(String(255))
    message = Column(Text)

    verified = Column(Boolean, default=False)
    verification_reason = Column(String(255))
    signature_type = Column(String(64))  # gpg, ssh, smime, github, unknown
    signature_key_id = Column(String(128))
    signer_username = Column(String(255))

    dco = Column(Boolean, default=False)
    policy_passed = Column(Boolean, default=False)

    timestamp = Column(DateTime, default=datetime.utcnow)

    repo = relationship("Repository")
    pr = relationship("PullRequest")

    def to_dict(self):
        return {
            "sha": self.sha,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "committer_name": self.committer_name,
            "committer_email": self.committer_email,
            "message": self.message,
            "verified": self.verified,
            "verification_reason": self.verification_reason,
            "signature_type": self.signature_type,
            "signature_key_id": self.signature_key_id,
            "signer_username": self.signer_username,
            "dco": self.dco,
            "policy_passed": self.policy_passed,
            "timestamp": self.timestamp.isoformat() + "Z" if self.timestamp else None,
        }


class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(64), index=True)
    delivery_guid = Column(String(64), index=True)
    payload_json = Column(Text)
    received_at = Column(DateTime, default=datetime.utcnow)

