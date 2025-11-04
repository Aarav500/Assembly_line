from typing import List, Dict, Any


def _resource_label(d: Dict[str, Any]) -> str:
    rtype = d.get('type')
    name = d.get('name')
    return f"{rtype}/{name}"


def build_remediation_suggestions(diffs: List[Dict[str, Any]], desired_state: Dict[str, Any], actual_state: Dict[str, Any], mode: str) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []

    for d in diffs:
        kind = d['kind']
        label = _resource_label(d)

        if mode == 'enforce_desired':
            if kind == 'missing_in_actual':
                desired_res = d.get('desired')
                suggestions.append({
                    'action': 'create_resource',
                    'target': label,
                    'description': f"Create {label} in environment to match desired state.",
                    'commands': _suggest_commands_create(desired_res)
                })
            elif kind == 'extra_in_actual':
                actual_res = d.get('actual')
                suggestions.append({
                    'action': 'delete_resource',
                    'target': label,
                    'description': f"Delete {label} from environment to match desired state.",
                    'commands': _suggest_commands_delete(actual_res)
                })
            elif kind == 'attribute_diff':
                detail = d.get('detail', {})
                suggestions.append({
                    'action': 'update_attribute',
                    'target': label,
                    'description': f"Update attribute {detail.get('path')} in environment to desired value.",
                    'commands': _suggest_commands_update(d.get('type'), d.get('name'), detail)
                })
        else:  # update_desired
            if kind == 'missing_in_actual':
                suggestions.append({
                    'action': 'update_desired_remove',
                    'target': label,
                    'description': f"Remove {label} from desired to match actual (resource not present in environment)."
                })
            elif kind == 'extra_in_actual':
                suggestions.append({
                    'action': 'update_desired_add',
                    'target': label,
                    'description': f"Add {label} to desired to match actual (resource exists in environment)."
                })
            elif kind == 'attribute_diff':
                detail = d.get('detail', {})
                suggestions.append({
                    'action': 'update_desired_attribute',
                    'target': label,
                    'description': f"Set desired {detail.get('path')} = {repr(detail.get('actual'))} to match actual."
                })

    return suggestions


def _suggest_commands_create(res: Dict[str, Any]) -> List[str]:
    rtype = res.get('type')
    name = res.get('name')
    # These are illustrative, adapt to your infra tool (kubectl, helm, terraform, etc.)
    return [
        f"# Create resource using your infra tool",
        f"# Example (kubectl):",
        f"kubectl apply -f <manifest-for-{rtype}-{name}>"
    ]


def _suggest_commands_delete(res: Dict[str, Any]) -> List[str]:
    rtype = res.get('type')
    name = res.get('name')
    return [
        f"# Delete resource using your infra tool",
        f"# Example (kubectl):",
        f"kubectl delete {rtype.lower()} {name}"
    ]


def _suggest_commands_update(rtype: str, name: str, detail: Dict[str, Any]) -> List[str]:
    path = detail.get('path')
    desired_value = detail.get('desired')
    return [
        f"# Patch resource attribute using your infra tool",
        f"# Example (kubectl):",
        f"kubectl patch {rtype.lower()} {name} --type merge -p '{{\"{path}\": {repr(desired_value)}}}'"
    ]

