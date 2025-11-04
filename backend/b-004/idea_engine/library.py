import json
from typing import List, Dict, Any, Optional
from .models import Template, Field
from .utils import build_env, base_context, validate_inputs

class IdeaLibrary:
    def __init__(self, templates: List[Template]):
        self._templates = {t.id: t for t in templates}
        self._env = build_env()

    @classmethod
    def from_file(cls, path: str) -> "IdeaLibrary":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        templates: List[Template] = []
        for td in data.get("templates", []):
            fields = [Field(**fd) for fd in td.get("fields", [])]
            t = Template(
                id=td["id"],
                name=td["name"],
                category=td["category"],
                description=td.get("description", ""),
                tags=td.get("tags", []),
                fields=fields,
                sections=td.get("sections", {}),
                version=str(td.get("version", data.get("version", "1.0")))
            )
            templates.append(t)
        return cls(templates)

    def categories(self) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        for t in self._templates.values():
            counts[t.category] = counts.get(t.category, 0) + 1
        return sorted([{"name": k, "count": v} for k, v in counts.items()], key=lambda x: x["name"].lower())

    def all(self) -> List[Template]:
        return list(self._templates.values())

    def get(self, template_id: str) -> Optional[Template]:
        return self._templates.get(template_id)

    def search(self, category: Optional[str] = None, query: Optional[str] = None) -> List[Template]:
        items = self.all()
        if category:
            items = [t for t in items if t.category.lower() == category.lower()]
        if query:
            q = query.lower()
            items = [t for t in items if q in t.name.lower() or q in t.description.lower() or any(q in tag.lower() for tag in t.tags)]
        items.sort(key=lambda t: (t.category.lower(), t.name.lower()))
        return items

    def render(self, template_id: str, inputs: Dict[str, Any], output_format: str = "markdown") -> Dict[str, Any]:
        t = self.get(template_id)
        if not t:
            raise KeyError(f"Unknown template: {template_id}")
        clean_inputs = validate_inputs(t.fields, inputs or {})
        ctx = base_context(clean_inputs)
        sections_out: Dict[str, str] = {}
        for key, tmpl in t.sections.items():
            jtmpl = self._env.from_string(tmpl)
            sections_out[key] = jtmpl.render(**ctx)
        combined = self._combine(sections_out, fmt=output_format)
        return {
            "sections": sections_out,
            "combined": combined,
            "meta": {
                "template": t.to_dict(summary=True),
                "inputs": clean_inputs,
                "format": output_format,
            }
        }

    @staticmethod
    def _combine(sections: Dict[str, str], fmt: str = "markdown") -> str:
        parts: List[str] = []
        for name, content in sections.items():
            if fmt == "markdown":
                parts.append(f"## {name.replace('_', ' ').title()}\n\n{content.strip()}\n")
            else:
                # plain text
                parts.append(f"{name.upper()}\n\n{content.strip()}\n")
        return "\n".join(parts).strip()

