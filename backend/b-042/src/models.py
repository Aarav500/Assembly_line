from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Team:
    size: int = 2
    skills: List[str] = field(default_factory=list)


@dataclass
class Project:
    name: str = ""
    description: str = ""
    goal: str = ""
    deadline_days: int = 30
    budget: Optional[float] = None
    team: Team = field(default_factory=Team)


@dataclass
class Strategy:
    bias: str = "time_to_market"  # time_to_market | quality | cost
    risk_tolerance: str = "medium"  # low | medium | high


@dataclass
class Constraints:
    must_include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    non_functional: List[str] = field(default_factory=list)


@dataclass
class FeatureInput:
    name: str
    description: str = ""
    value: Optional[float] = None  # 0-10
    effort: Optional[float] = None  # person-days
    risk: Optional[float] = None  # 0-10
    dependencies: List[str] = field(default_factory=list)
    is_core: bool = False
    tags: List[str] = field(default_factory=list)


def parse_project(d: Dict[str, Any]) -> Project:
    team_data = d.get("team", {}) or {}
    team = Team(size=int(team_data.get("size", 2)), skills=list(team_data.get("skills", [])))
    return Project(
        name=str(d.get("name", "")),
        description=str(d.get("description", "")),
        goal=str(d.get("goal", "")),
        deadline_days=int(d.get("deadline_days", 30)),
        budget=d.get("budget", None),
        team=team,
    )


def parse_strategy(d: Dict[str, Any]) -> Strategy:
    return Strategy(
        bias=str(d.get("bias", "time_to_market")),
        risk_tolerance=str(d.get("risk_tolerance", "medium")),
    )


def parse_constraints(d: Dict[str, Any]) -> Constraints:
    return Constraints(
        must_include=list(d.get("must_include", []) or []),
        exclude=list(d.get("exclude", []) or []),
        non_functional=list(d.get("non_functional", []) or []),
    )


def parse_features(arr: List[Dict[str, Any]]) -> List[FeatureInput]:
    out: List[FeatureInput] = []
    for f in arr or []:
        out.append(
            FeatureInput(
                name=str(f.get("name")),
                description=str(f.get("description", "")),
                value=(float(f["value"]) if f.get("value") is not None else None),
                effort=(float(f["effort"]) if f.get("effort") is not None else None),
                risk=(float(f["risk"]) if f.get("risk") is not None else None),
                dependencies=list(f.get("dependencies", []) or []),
                is_core=bool(f.get("is_core", False)),
                tags=list(f.get("tags", []) or []),
            )
        )
    return out

