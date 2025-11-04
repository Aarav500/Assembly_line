from typing import List, Dict, Optional
from pydantic import BaseModel, Field, HttpUrl


class Artifact(BaseModel):
    name: str
    digest: Dict[str, str]
    uri: Optional[str] = None


class GitInfo(BaseModel):
    commit: str = Field(..., description="Git commit SHA")
    ref: str = Field(..., description="Git ref, e.g., refs/heads/main")
    repo: str = Field(..., description="Repository URL or identifier")


class CIInfo(BaseModel):
    name: str
    run_id: str
    url: Optional[str] = None


class BuilderInfo(BaseModel):
    id: str
    ci: CIInfo


class AttestRequest(BaseModel):
    build_id: str
    project: str
    git: GitInfo
    builder: BuilderInfo
    artifacts: List[Artifact]
    predicates: Optional[Dict] = None

