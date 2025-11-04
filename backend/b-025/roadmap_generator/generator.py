from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import math
import re


DATE_FMT = "%Y-%m-%d"


def to_date(s: Optional[str]) -> datetime:
    if not s:
        return datetime.utcnow()
    return datetime.strptime(s, DATE_FMT)


def to_iso(d: datetime) -> str:
    return d.strftime(DATE_FMT)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


@dataclass
class Milestone:
    id: str
    title: str
    description: str
    due_date: str
    owner: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class Phase:
    key: str
    name: str
    stage: str
    start_date: str
    end_date: str
    weeks: int
    milestones: List[Milestone]


@dataclass
class Roadmap:
    project_name: str
    target: str
    start_date: str
    forecast_end_date: str
    total_weeks: int
    complexity: str
    team_size: int
    constraints: List[str]
    risk_level: str
    phases: List[Phase]
    summary: Dict[str, Any]


PHASE_BLUEPRINTS = [
    {
        "key": "discovery",
        "name": "Discovery",
        "stage": "foundation",
        "base_weeks": 2,
        "owner": "PM",
        "tasks": [
            {"title": "Project Kickoff", "ratio": 0.1, "owner": "PM"},
            {"title": "Research Plan Ready", "ratio": 0.4, "owner": "PM"},
            {"title": "Discovery Complete", "ratio": 1.0, "owner": "PM"},
        ],
    },
    {
        "key": "architecture_planning",
        "name": "Architecture & Planning",
        "stage": "foundation",
        "base_weeks": 2,
        "owner": "Tech Lead",
        "tasks": [
            {"title": "Architecture Draft", "ratio": 0.5, "owner": "Tech Lead"},
            {"title": "Backlog & Slicing", "ratio": 0.8, "owner": "PM"},
            {"title": "Plan Sign-off", "ratio": 1.0, "owner": "PM"},
        ],
    },
    {
        "key": "setup",
        "name": "Environment & CI Setup",
        "stage": "foundation",
        "base_weeks": 1,
        "owner": "DevOps",
        "tasks": [
            {"title": "Repo, CI/CD, Linting", "ratio": 0.5, "owner": "DevOps"},
            {"title": "Environments Ready", "ratio": 1.0, "owner": "DevOps"},
        ],
    },
    {
        "key": "mvp_build",
        "name": "MVP Build",
        "stage": "mvp",
        "base_weeks": 4,
        "owner": "Tech Lead",
        "tasks": [
            {"title": "Core Feature Slice 1", "ratio": 0.3, "owner": "Tech Lead"},
            {"title": "Core Feature Slice 2", "ratio": 0.6, "owner": "Tech Lead"},
            {"title": "MVP Feature Complete", "ratio": 1.0, "owner": "Tech Lead"},
        ],
    },
    {
        "key": "qa_hardening",
        "name": "QA & Hardening",
        "stage": "mvp",
        "base_weeks": 2,
        "owner": "QA Lead",
        "tasks": [
            {"title": "Test Plan Ready", "ratio": 0.3, "owner": "QA Lead"},
            {"title": "QA Pass", "ratio": 0.9, "owner": "QA Lead"},
            {"title": "UAT Sign-off", "ratio": 1.0, "owner": "PM"},
        ],
    },
    {
        "key": "release_mvp",
        "name": "Release: MVP",
        "stage": "mvp",
        "base_weeks": 0,
        "owner": "PM",
        "tasks": [
            {"title": "MVP Released", "ratio": 0.0, "owner": "PM"},
        ],
    },
    {
        "key": "phase1_build",
        "name": "Phase 1 Features",
        "stage": "phase1",
        "base_weeks": 4,
        "owner": "Tech Lead",
        "tasks": [
            {"title": "Phase 1 Features Complete", "ratio": 1.0, "owner": "Tech Lead"},
        ],
    },
    {
        "key": "polish_analytics",
        "name": "Polish & Analytics",
        "stage": "phase1",
        "base_weeks": 1,
        "owner": "Tech Lead",
        "tasks": [
            {"title": "Analytics & Telemetry Live", "ratio": 1.0, "owner": "Tech Lead"},
        ],
    },
    {
        "key": "release_phase1",
        "name": "Release: Phase 1",
        "stage": "phase1",
        "base_weeks": 0,
        "owner": "PM",
        "tasks": [
            {"title": "Phase 1 Released", "ratio": 0.0, "owner": "PM"},
        ],
    },
    {
        "key": "scale_performance",
        "name": "Scale: Performance & Resilience",
        "stage": "scale",
        "base_weeks": 3,
        "owner": "Tech Lead",
        "tasks": [
            {"title": "Load & Perf Benchmarks", "ratio": 0.7, "owner": "Tech Lead"},
            {"title": "Performance Targets Met", "ratio": 1.0, "owner": "Tech Lead"},
        ],
    },
    {
        "key": "sre_observability",
        "name": "SRE & Observability",
        "stage": "scale",
        "base_weeks": 2,
        "owner": "SRE Lead",
        "tasks": [
            {"title": "Observability Complete", "ratio": 0.7, "owner": "SRE Lead"},
            {"title": "SLOs & Runbooks Ready", "ratio": 1.0, "owner": "SRE Lead"},
        ],
    },
    {
        "key": "release_scale",
        "name": "Release: Scale",
        "stage": "scale",
        "base_weeks": 0,
        "owner": "PM",
        "tasks": [
            {"title": "Scale Release", "ratio": 0.0, "owner": "PM"},
        ],
    },
]


def stage_order_for_target(target: str) -> List[str]:
    if target in ("mvp",):
        return ["foundation", "mvp"]
    if target in ("phase1",):
        return ["foundation", "mvp", "phase1"]
    if target in ("scale", "all"):
        return ["foundation", "mvp", "phase1", "scale"]
    return ["foundation", "mvp"]


def complexity_multiplier(level: str) -> float:
    return {"low": 0.85, "medium": 1.0, "high": 1.25}.get(level, 1.0)


def team_efficiency(team_size: int) -> float:
    # Diminishing returns; baseline 0.6 for very small teams
    eff = 0.6 + 0.1 * max(0, team_size)
    return max(0.5, min(1.5, eff))


def effective_weeks(base_weeks: int, complexity: str, team_size: int) -> int:
    if base_weeks == 0:
        return 0
    eff = base_weeks * complexity_multiplier(complexity) / team_efficiency(team_size)
    return int(math.ceil(eff))


def risk_level_for(complexity: str, constraints: List[str]) -> str:
    c = len([x for x in constraints if x.strip()])
    if complexity == 'high' or c >= 3:
        return 'high'
    if c >= 1:
        return 'medium'
    return 'low'


def validate_and_normalize_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    project_name = str(payload.get('project_name') or 'Untitled Project').strip() or 'Untitled Project'
    start_date_raw = payload.get('start_date')
    try:
        start_dt = to_date(start_date_raw) if start_date_raw else datetime.utcnow()
    except Exception:
        raise ValueError('Invalid start_date. Use YYYY-MM-DD.')

    complexity = str(payload.get('complexity') or 'medium').lower()
    if complexity not in ('low', 'medium', 'high'):
        raise ValueError('complexity must be one of: low, medium, high')

    target = str(payload.get('target') or 'mvp').lower()
    if target not in ('mvp', 'phase1', 'scale', 'all'):
        raise ValueError('target must be one of: mvp, phase1, scale, all')

    team_size = payload.get('team_size', 5)
    try:
        team_size = int(team_size)
    except Exception:
        raise ValueError('team_size must be an integer')
    if team_size < 1:
        team_size = 1

    constraints = payload.get('constraints') or []
    if not isinstance(constraints, list):
        raise ValueError('constraints must be a list of strings')

    domains = payload.get('domains') or []
    if not isinstance(domains, list):
        raise ValueError('domains must be a list of strings')

    return {
        'project_name': project_name,
        'start_date': to_iso(start_dt),
        'complexity': complexity,
        'target': target,
        'team_size': team_size,
        'constraints': [str(x) for x in constraints],
        'domains': [str(d) for d in domains],
    }


def generate_roadmap(params: Dict[str, Any]) -> Dict[str, Any]:
    start_dt = to_date(params['start_date'])
    target = params['target']
    complexity = params['complexity']
    team_size = params['team_size']
    constraints = params['constraints']

    stages = stage_order_for_target(target)
    filtered = [p for p in PHASE_BLUEPRINTS if p['stage'] in stages]

    phases: List[Phase] = []
    cursor = start_dt
    total_weeks = 0
    all_milestones: Dict[str, Milestone] = {}

    for blueprint in filtered:
        ew = effective_weeks(blueprint['base_weeks'], complexity, team_size)
        phase_start = cursor
        phase_days = ew * 7
        if ew > 0:
            phase_end = phase_start + timedelta(days=phase_days - 1)
            cursor = phase_end + timedelta(days=1)
        else:
            phase_end = phase_start
            # Advance cursor by 0 days for zero-week phase, keep same day
        total_weeks += ew

        milestones: List[Milestone] = []
        for t in blueprint['tasks']:
            ratio = max(0.0, min(1.0, float(t.get('ratio', 1.0))))
            if ew == 0:
                due = phase_start
            else:
                offset_days = int(round((phase_days - 1) * ratio))
                due = phase_start + timedelta(days=offset_days)
            title = t['title']
            mid = slugify(f"{blueprint['key']}-{title}")
            m = Milestone(
                id=mid,
                title=title,
                description=f"{title} within {blueprint['name']} phase",
                due_date=to_iso(due),
                owner=t.get('owner') or blueprint['owner'],
                tags=[blueprint['stage'], blueprint['key']] + [slugify(c) for c in params.get('domains', [])],
                dependencies=[],
            )
            milestones.append(m)
            all_milestones[mid] = m

        phase = Phase(
            key=blueprint['key'],
            name=blueprint['name'],
            stage=blueprint['stage'],
            start_date=to_iso(phase_start),
            end_date=to_iso(phase_end),
            weeks=ew,
            milestones=milestones,
        )
        phases.append(phase)

    # Add simple linear dependencies: each milestone depends on the last milestone of previous phase
    prev_last_id: Optional[str] = None
    for phase in phases:
        for m in phase.milestones:
            if prev_last_id:
                m.dependencies.append(prev_last_id)
        if phase.milestones:
            prev_last_id = phase.milestones[-1].id

    forecast_end = phases[-1].end_date if phases else to_iso(start_dt)

    risk = risk_level_for(complexity, constraints)

    summary = {
        'total_phases': len(phases),
        'total_milestones': sum(len(p.milestones) for p in phases),
        'notes': _summary_notes(risk, stages, params.get('domains', []), constraints),
    }

    roadmap = Roadmap(
        project_name=params['project_name'],
        target=target,
        start_date=params['start_date'],
        forecast_end_date=forecast_end,
        total_weeks=total_weeks,
        complexity=complexity,
        team_size=team_size,
        constraints=constraints,
        risk_level=risk,
        phases=phases,
        summary=summary,
    )

    return _serialize_roadmap(roadmap)


def _summary_notes(risk: str, stages: List[str], domains: List[str], constraints: List[str]) -> List[str]:
    notes = []
    if 'mvp' in stages and 'scale' not in stages:
        notes.append('Focus on rapid MVP delivery. Defer non-essential optimizations.')
    if 'scale' in stages:
        notes.append('Include performance and SRE readiness before scale release.')
    if domains:
        notes.append(f"Domains in scope: {', '.join(domains)}")
    if constraints:
        notes.append(f"Constraints to track: {', '.join(constraints)}")
    notes.append(f"Overall risk assessed as {risk}.")
    return notes


def _serialize_roadmap(roadmap: Roadmap) -> Dict[str, Any]:
    return {
        'project_name': roadmap.project_name,
        'target': roadmap.target,
        'start_date': roadmap.start_date,
        'forecast_end_date': roadmap.forecast_end_date,
        'total_weeks': roadmap.total_weeks,
        'complexity': roadmap.complexity,
        'team_size': roadmap.team_size,
        'constraints': roadmap.constraints,
        'risk_level': roadmap.risk_level,
        'phases': [
            {
                'key': p.key,
                'name': p.name,
                'stage': p.stage,
                'start_date': p.start_date,
                'end_date': p.end_date,
                'weeks': p.weeks,
                'milestones': [
                    {
                        'id': m.id,
                        'title': m.title,
                        'description': m.description,
                        'due_date': m.due_date,
                        'owner': m.owner,
                        'tags': m.tags,
                        'dependencies': m.dependencies,
                    }
                    for m in p.milestones
                ],
            }
            for p in roadmap.phases
        ],
        'summary': roadmap.summary,
    }

