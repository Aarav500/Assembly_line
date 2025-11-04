import uuid
from typing import Any, Dict, List, Optional
from .utils import canonicalize_json_obj

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
SLSA_PREDICATE_TYPE = "https://slsa.dev/provenance/v1"


def isoformat_or_none(ts: Optional[str]) -> Optional[str]:
    if ts is None:
        return None
    return ts


def make_provenance_statement(
    subjects: List[Dict[str, Any]],
    build_type: str,
    external_parameters: Dict[str, Any],
    internal_parameters: Optional[Dict[str, Any]],
    resolved_dependencies: List[Dict[str, Any]],
    builder_id: str,
    builder_version: Optional[Dict[str, str]] = None,
    invocation_id: Optional[str] = None,
    started_on: Optional[str] = None,
    finished_on: Optional[str] = None,
) -> Dict[str, Any]:
    predicate = {
        "buildDefinition": {
            "buildType": build_type,
            "externalParameters": external_parameters or {},
        },
        "runDetails": {
            "builder": {
                "id": builder_id,
            },
            "metadata": {},
            "byproducts": [],
        },
    }

    if internal_parameters is not None:
        predicate["buildDefinition"]["internalParameters"] = internal_parameters

    if resolved_dependencies:
        predicate["buildDefinition"]["resolvedDependencies"] = resolved_dependencies

    if builder_version:
        predicate["runDetails"]["builder"]["version"] = builder_version

    md = predicate["runDetails"]["metadata"]
    if invocation_id:
        md["invocationId"] = invocation_id
    else:
        md["invocationId"] = str(uuid.uuid4())
    if started_on:
        md["startedOn"] = isoformat_or_none(started_on)
    if finished_on:
        md["finishedOn"] = isoformat_or_none(finished_on)

    statement = {
        "_type": STATEMENT_TYPE,
        "subject": subjects,
        "predicateType": SLSA_PREDICATE_TYPE,
        "predicate": predicate,
    }
    return statement


def canonicalize_json(obj: Dict[str, Any]) -> bytes:
    return canonicalize_json_obj(obj)

