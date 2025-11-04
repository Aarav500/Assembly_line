import os
from typing import Optional
from sqlalchemy.orm import Session

from models import Project, Requirement
from analysis.code_parser import parse_project_python


def register_project(db: Session, name: str, root_path: str) -> Project:
    proj = db.query(Project).filter_by(name=name).one_or_none()
    if proj is None:
        proj = Project(name=name, root_path=root_path)
        db.add(proj)
        db.commit()
    else:
        proj.root_path = root_path
        db.commit()

    ingest_requirements(db, proj)
    return proj


def ingest_requirements(db: Session, project: Project):
    # Clear previous
    db.query(Requirement).filter(Requirement.project_id == project.id).delete(synchronize_session=False)
    req_paths = [
        os.path.join(project.root_path, 'requirements.txt'),
        os.path.join(project.root_path, 'reqs.txt'),
    ]
    for p in req_paths:
        if os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        name, spec = parse_req_line(line)
                        db.add(Requirement(project_id=project.id, name=name, spec=spec))
            except Exception:
                pass
    db.commit()


def parse_req_line(line: str) -> tuple[str, str]:
    # Very simple requirements parser
    seps = ['==', '>=', '<=', '>', '<', '~=', '!=']
    for sep in seps:
        if sep in line:
            name, spec = line.split(sep, 1)
            return name.strip(), f"{sep}{spec.strip()}"
    return line.strip(), ''


def analyze_project(db: Session, project_id: int) -> Optional[Project]:
    proj = db.query(Project).filter_by(id=project_id).one_or_none()
    if not proj:
        return None
    parse_project_python(db, proj)
    ingest_requirements(db, proj)
    return proj


def analyze_all_projects(db: Session):
    projects = db.query(Project).all()
    for p in projects:
        analyze_project(db, p.id)


def list_projects(db: Session) -> list[dict]:
    projects = db.query(Project).all()
    return [{"id": p.id, "name": p.name, "path": p.root_path, "created_at": p.created_at.isoformat()} for p in projects]


def get_project_details(db: Session, project_id: int) -> Optional[dict]:
    p = db.query(Project).filter_by(id=project_id).one_or_none()
    if not p:
        return None
    func_count = db.query(Project).filter_by(id=project_id).join(Project.functions).count() if p.functions else 0
    import_count = db.query(Project).filter_by(id=project_id).join(Project.imports).count() if p.imports else 0
    reqs = db.query(Requirement).filter_by(project_id=project_id).all()
    return {
        "id": p.id,
        "name": p.name,
        "path": p.root_path,
        "created_at": p.created_at.isoformat(),
        "function_count": func_count,
        "import_entries": import_count,
        "requirements": [{"name": r.name, "spec": r.spec} for r in reqs]
    }

