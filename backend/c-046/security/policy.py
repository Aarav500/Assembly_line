from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


def _norm_list(values):
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return [str(v) for v in values if v is not None]


def _join_sources(values: List[str]) -> str:
    return " ".join(sorted(set(values), key=lambda x: x))


@dataclass
class CSPPolicyConfig:
    default_src: List[str] = field(default_factory=list)
    script_src: List[str] = field(default_factory=list)
    style_src: List[str] = field(default_factory=list)
    img_src: List[str] = field(default_factory=list)
    font_src: List[str] = field(default_factory=list)
    connect_src: List[str] = field(default_factory=list)
    frame_src: List[str] = field(default_factory=list)
    object_src: List[str] = field(default_factory=list)
    base_uri: List[str] = field(default_factory=list)
    form_action: List[str] = field(default_factory=list)
    upgrade_insecure_requests: bool = False
    block_all_mixed_content: bool = False
    report_uri: Optional[str] = None
    report_to: Optional[str] = None

    def to_header(self) -> str:
        parts = []
        def add(name, values):
            if values:
                parts.append(f"{name} {_join_sources(values)}")
        add("default-src", self.default_src)
        add("script-src", self.script_src)
        add("style-src", self.style_src)
        add("img-src", self.img_src)
        add("font-src", self.font_src)
        add("connect-src", self.connect_src)
        add("frame-src", self.frame_src)
        add("object-src", self.object_src)
        add("base-uri", self.base_uri)
        add("form-action", self.form_action)
        if self.upgrade_insecure_requests:
            parts.append("upgrade-insecure-requests")
        if self.block_all_mixed_content:
            parts.append("block-all-mixed-content")
        if self.report_uri:
            parts.append(f"report-uri {self.report_uri}")
        if self.report_to:
            parts.append(f"report-to {self.report_to}")
        return "; ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_src": self.default_src,
            "script_src": self.script_src,
            "style_src": self.style_src,
            "img_src": self.img_src,
            "font_src": self.font_src,
            "connect_src": self.connect_src,
            "frame_src": self.frame_src,
            "object_src": self.object_src,
            "base_uri": self.base_uri,
            "form_action": self.form_action,
            "upgrade_insecure_requests": self.upgrade_insecure_requests,
            "block_all_mixed_content": self.block_all_mixed_content,
            "report_uri": self.report_uri,
            "report_to": self.report_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CSPPolicyConfig":
        if data is None:
            return cls()
        return cls(
            default_src=_norm_list(data.get("default_src")),
            script_src=_norm_list(data.get("script_src")),
            style_src=_norm_list(data.get("style_src")),
            img_src=_norm_list(data.get("img_src")),
            font_src=_norm_list(data.get("font_src")),
            connect_src=_norm_list(data.get("connect_src")),
            frame_src=_norm_list(data.get("frame_src")),
            object_src=_norm_list(data.get("object_src")),
            base_uri=_norm_list(data.get("base_uri")),
            form_action=_norm_list(data.get("form_action")),
            upgrade_insecure_requests=bool(data.get("upgrade_insecure_requests", False)),
            block_all_mixed_content=bool(data.get("block_all_mixed_content", False)),
            report_uri=data.get("report_uri"),
            report_to=data.get("report_to"),
        )

    def merge(self, other: "CSPPolicyConfig") -> "CSPPolicyConfig":
        return CSPPolicyConfig(
            default_src=list(set(self.default_src + other.default_src)),
            script_src=list(set(self.script_src + other.script_src)),
            style_src=list(set(self.style_src + other.style_src)),
            img_src=list(set(self.img_src + other.img_src)),
            font_src=list(set(self.font_src + other.font_src)),
            connect_src=list(set(self.connect_src + other.connect_src)),
            frame_src=list(set(self.frame_src + other.frame_src)),
            object_src=list(set(self.object_src + other.object_src)),
            base_uri=list(set(self.base_uri + other.base_uri)),
            form_action=list(set(self.form_action + other.form_action)),
            upgrade_insecure_requests=self.upgrade_insecure_requests or other.upgrade_insecure_requests,
            block_all_mixed_content=self.block_all_mixed_content or other.block_all_mixed_content,
            report_uri=self.report_uri or other.report_uri,
            report_to=self.report_to or other.report_to,
        )


@dataclass
class CORSConfig:
    mode: str = "strict"  # strict | public | allowlist
    allow_origins: List[str] = field(default_factory=list)
    allow_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE"])
    allow_headers: List[str] = field(default_factory=lambda: ["Content-Type", "Authorization"]) 
    expose_headers: List[str] = field(default_factory=list)
    allow_credentials: bool = False
    max_age: int = 600

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "allow_origins": self.allow_origins,
            "allow_methods": self.allow_methods,
            "allow_headers": self.allow_headers,
            "expose_headers": self.expose_headers,
            "allow_credentials": self.allow_credentials,
            "max_age": self.max_age,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CORSConfig":
        if data is None:
            return cls()
        mode = data.get("mode", "strict")
        if mode not in ("strict", "public", "allowlist"):
            raise ValueError("mode must be 'strict', 'public', or 'allowlist'")
        return cls(
            mode=mode,
            allow_origins=_norm_list(data.get("allow_origins")),
            allow_methods=_norm_list(data.get("allow_methods")) or ["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=_norm_list(data.get("allow_headers")) or ["Content-Type", "Authorization"],
            expose_headers=_norm_list(data.get("expose_headers")),
            allow_credentials=bool(data.get("allow_credentials", False)),
            max_age=int(data.get("max_age", 600)),
        )

