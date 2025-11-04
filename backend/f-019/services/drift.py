import json
import os
from typing import Dict, Any, List, Tuple
from copy import deepcopy

from config import LOCAL_DESIRED_PATH, GITHUB_REPO, GITHUB_DESIRED_PATH
from services.github_client import GitHubClient


# Desired/Actual schema expected:
# {
#   "resources": [
#       {
#           "type": "Service",
#           "name": "api",
#           "attributes": {
#               "replicas": 3,
#               "image": "example/api:1.2.3",
#               "env": {"ENV": "prod"}
#           }
#       },
#       ...
#   ]
# }


def _index_resources(state: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    idx: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for res in state.get('resources', []):
        rtype = res.get('type')
        name = res.get('name')
        if rtype is None or name is None:
            # Skip malformed
            continue
        idx.setdefault(rtype, {})[name] = res
    return idx


def _compare_attributes(desired_attrs: Dict[str, Any], actual_attrs: Dict[str, Any], path_prefix: str = '') -> List[Dict[str, Any]]:
    diffs: List[Dict[str, Any]] = []
    keys = set(desired_attrs.keys()) | set(actual_attrs.keys())
    for k in sorted(keys):
        dpresent = k in desired_attrs
        apresent = k in actual_attrs
        subpath = f"{path_prefix}.{k}" if path_prefix else k
        if not dpresent and apresent:
            diffs.append({'path': subpath, 'kind': 'extra_attribute', 'actual': actual_attrs.get(k)})
        elif dpresent and not apresent:
            diffs.append({'path': subpath, 'kind': 'missing_attribute', 'desired': desired_attrs.get(k)})
        else:
            dv = desired_attrs.get(k)
            av = actual_attrs.get(k)
            if isinstance(dv, dict) and isinstance(av, dict):
                diffs.extend(_compare_attributes(dv, av, subpath))
            elif dv != av:
                diffs.append({'path': subpath, 'kind': 'value_mismatch', 'desired': dv, 'actual': av})
    return diffs


def compute_drift(desired_state: Dict[str, Any], actual_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    diffs: List[Dict[str, Any]] = []
    didx = _index_resources(desired_state)
    aidx = _index_resources(actual_state)

    all_types = set(didx.keys()) | set(aidx.keys())
    for rtype in sorted(all_types):
        dnames = set(didx.get(rtype, {}).keys())
        anames = set(aidx.get(rtype, {}).keys())

        # Missing in actual
        for name in sorted(dnames - anames):
            diffs.append({
                'kind': 'missing_in_actual',
                'type': rtype,
                'name': name,
                'desired': didx[rtype][name]
            })

        # Extra in actual
        for name in sorted(anames - dnames):
            diffs.append({
                'kind': 'extra_in_actual',
                'type': rtype,
                'name': name,
                'actual': aidx[rtype][name]
            })

        # Attribute diffs
        for name in sorted(dnames & anames):
            dres = didx[rtype][name]
            ares = aidx[rtype][name]
            dattrs = dres.get('attributes', {})
            aattrs = ares.get('attributes', {})
            attr_diffs = _compare_attributes(dattrs, aattrs)
            for ad in attr_diffs:
                diffs.append({
                    'kind': 'attribute_diff',
                    'type': rtype,
                    'name': name,
                    'path': ad['path'],
                    'detail': ad
                })

    return diffs


def load_desired_state() -> Tuple[Dict[str, Any], str]:
    if GITHUB_REPO:
        gh = GitHubClient()
        content = gh.get_file_text(gh.desired_path())
        try:
            data = json.loads(content)
        except Exception as e:
            raise RuntimeError(f"Failed to parse desired state JSON from GitHub: {e}")
        return data, f"github:{GITHUB_REPO}:{GITHUB_DESIRED_PATH}"
    else:
        if not os.path.exists(LOCAL_DESIRED_PATH):
            raise FileNotFoundError(f"Desired state file not found at {LOCAL_DESIRED_PATH}")
        with open(LOCAL_DESIRED_PATH, 'r') as f:
            return json.load(f), f"local:{LOCAL_DESIRED_PATH}"


def save_last_drift(result: Dict[str, Any]):
    os.makedirs('data', exist_ok=True)
    with open(os.path.join('data', 'last_drift.json'), 'w') as f:
        json.dump(result, f, indent=2)


def load_last_drift():
    path = os.path.join('data', 'last_drift.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)


def apply_drift_to_desired(desired: Dict[str, Any], actual: Dict[str, Any], diffs: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Produce a new desired by aligning to actual for affected resources
    new_desired = deepcopy(desired)
    didx = _index_resources(new_desired)
    aidx = _index_resources(actual)

    # Ensure the resources list exists
    if 'resources' not in new_desired or not isinstance(new_desired['resources'], list):
        new_desired['resources'] = []

    # Track which resource keys need to be replaced or removed
    replace_keys = set()
    add_keys = set()
    remove_keys = set()

    for d in diffs:
        rkey = (d.get('type'), d.get('name'))
        if d['kind'] == 'missing_in_actual':
            # actual lacks resource; aligning desired to actual means removing from desired
            remove_keys.add(rkey)
        elif d['kind'] == 'extra_in_actual':
            # actual has extra; aligning desired to actual means adding to desired
            add_keys.add(rkey)
        elif d['kind'] == 'attribute_diff':
            # replace resource desired with actual version
            replace_keys.add(rkey)

    # Remove resources from desired
    if remove_keys:
        new_list = []
        for res in new_desired.get('resources', []):
            rkey = (res.get('type'), res.get('name'))
            if rkey in remove_keys:
                continue
            new_list.append(res)
        new_desired['resources'] = new_list

    # Add resources from actual
    for rtype, name in add_keys:
        if rtype in aidx and name in aidx[rtype]:
            new_desired['resources'].append(deepcopy(aidx[rtype][name]))

    # Replace attributes from actual
    # Build an index again since we may have modified list
    ndx = _index_resources(new_desired)
    for rtype, name in replace_keys:
        if rtype in aidx and name in aidx[rtype]:
            if rtype in ndx and name in ndx[rtype]:
                ndx[rtype][name]['attributes'] = deepcopy(aidx[rtype][name].get('attributes', {}))

    return new_desired

