from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Policy:
    required_tee: List[str] = field(default_factory=list)  # e.g., ["tdx", "sev-snp", "nitro"]
    vendor: List[str] = field(default_factory=list)  # e.g., ["intel", "amd", "aws"]
    min_svn: int = 0
    allowed_mrenclave: List[str] = field(default_factory=list)
    allowed_mrsigner: List[str] = field(default_factory=list)
    allow_debug: bool = False
    require_hw_protected: bool = True


def policy_from_dict(d: Dict[str, Any]) -> Policy:
    return Policy(
        required_tee=[x.lower() for x in d.get("required_tee", [])],
        vendor=[x.lower() for x in d.get("vendor", [])],
        min_svn=int(d.get("min_svn", 0)),
        allowed_mrenclave=[x.lower() for x in d.get("allowed_mrenclave", [])],
        allowed_mrsigner=[x.lower() for x in d.get("allowed_mrsigner", [])],
        allow_debug=bool(d.get("allow_debug", False)),
        require_hw_protected=bool(d.get("require_hw_protected", True)),
    )

