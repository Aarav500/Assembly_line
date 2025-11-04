from dataclasses import dataclass, field as dataclass_field
from typing import List, Dict, Any, Optional

@dataclass
class Field:
    name: str
    label: str
    type: str = "text"  # text, textarea, number, select
    required: bool = False
    default: Any = None
    options: Optional[List[Any]] = None
    example: Optional[str] = None
    help: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "options": self.options,
            "example": self.example,
            "help": self.help,
        }

@dataclass
class Template:
    id: str
    name: str
    category: str
    description: str
    tags: List[str]
    fields: List[Field]
    sections: Dict[str, str]
    version: str = "1.0"

    def to_dict(self, summary: bool = False) -> Dict[str, Any]:
        base = {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "tags": self.tags,
            "version": self.version,
        }
        if summary:
            return base
        base["fields"] = [f.to_dict() for f in self.fields]
        base["sections"] = list(self.sections.keys())
        return base

