from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional, Tuple


@dataclass
class Field:
    name: str
    type: str
    primary_key: bool = False
    required: bool = False
    unique: bool = False
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    max_length: Optional[int] = None
    format: Optional[str] = None
    default: Optional[object] = None


@dataclass
class Relation:
    type: str  # one-to-one, one-to-many, many-to-one, many-to-many
    target: str
    foreign_key: Optional[str] = None
    backref: Optional[str] = None
    description: Optional[str] = None
    via: Optional[str] = None  # join table for many-to-many


@dataclass
class Entity:
    name: str
    description: Optional[str] = None
    fields: Dict[str, Field] = dc_field(default_factory=dict)
    relations: List[Relation] = dc_field(default_factory=list)


SUPPORTED_REL_TYPES = {"one-to-one", "one-to-many", "many-to-one", "many-to-many"}


BASIC_TYPE_MAP = {
    "string": {"type": "string"},
    "text": {"type": "string"},
    "integer": {"type": "integer"},
    "number": {"type": "number"},
    "float": {"type": "number", "format": "float"},
    "decimal": {"type": "number"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "format": "date"},
    "datetime": {"type": "string", "format": "date-time"},
    "uuid": {"type": "string", "format": "uuid"},
    "object": {"type": "object"},
    "array": {"type": "array"},
    "enum": {"type": "string"},
}


def map_field_to_jsonschema(f: Field) -> Dict:
    base = BASIC_TYPE_MAP.get(f.type, {"type": "string"}).copy()
    if f.enum:
        base["enum"] = f.enum
    if f.max_length and base.get("type") == "string":
        base["maxLength"] = f.max_length
    if f.format and base.get("type") == "string":
        base["format"] = f.format
    if f.description:
        base["description"] = f.description
    if f.default is not None:
        base["default"] = f.default
    return base


def map_field_to_mermaid_type(f: Field) -> str:
    t = f.type.lower()
    mapping = {
        "integer": "INT",
        "number": "NUM",
        "float": "FLOAT",
        "decimal": "DECIMAL",
        "boolean": "BOOL",
        "date": "DATE",
        "datetime": "DATETIME",
        "uuid": "UUID",
        "text": "TEXT",
        "string": "STRING",
        "object": "OBJECT",
        "array": "ARRAY",
        "enum": "ENUM",
    }
    return mapping.get(t, t.upper())


def pluralize(name: str) -> str:
    n = name.strip()
    if n.endswith("y") and len(n) > 1 and n[-2] not in "aeiou":
        return n[:-1] + "ies"
    if n.endswith("s"):
        return n + "es"
    return n + "s"


def cardinality_symbols(relation_type: str) -> Tuple[str, str]:
    # Returns (left, right) side symbols for Mermaid ER
    # A left -- right B
    rt = relation_type.lower()
    if rt == "one-to-one":
        return ("||", "||")
    if rt == "one-to-many":
        return ("||", "o{")
    if rt == "many-to-one":
        return ("}o", "||")
    if rt == "many-to-many":
        return ("}o", "o{")
    return ("||", "o{")


def get_primary_key_field(entity: Entity) -> Field:
    for f in entity.fields.values():
        if f.primary_key:
            return f
    # fallback to id if exists, else create default id
    if "id" in entity.fields:
        return entity.fields["id"]
    # Create a default id field if missing
    default_id = Field(name="id", type="integer", primary_key=True, required=True)
    entity.fields["id"] = default_id
    return default_id


def parse_entities_spec(spec: Dict) -> Dict[str, Entity]:
    if "entities" not in spec or not isinstance(spec["entities"], dict):
        raise ValueError("Spec must include an 'entities' object")

    entities: Dict[str, Entity] = {}

    for name, edef in spec["entities"].items():
        if not isinstance(edef, dict):
            raise ValueError(f"Entity '{name}' definition must be an object")
        e = Entity(name=name, description=edef.get("description"))
        # fields
        fields_def = edef.get("fields", {}) or {}
        if not isinstance(fields_def, dict):
            raise ValueError(f"Entity '{name}'.fields must be an object")
        for fname, fdef in fields_def.items():
            if not isinstance(fdef, dict):
                raise ValueError(f"Entity '{name}' field '{fname}' must be an object")
            f = Field(
                name=fname,
                type=str(fdef.get("type", "string")).lower(),
                primary_key=bool(fdef.get("primary_key", False)),
                required=bool(fdef.get("required", False)),
                unique=bool(fdef.get("unique", False)),
                description=fdef.get("description"),
                enum=fdef.get("enum"),
                max_length=fdef.get("max_length"),
                format=fdef.get("format"),
                default=fdef.get("default"),
            )
            e.fields[fname] = f
        # ensure a primary key exists
        _ = get_primary_key_field(e)

        # relations
        rels_def = edef.get("relations", []) or []
        if not isinstance(rels_def, list):
            raise ValueError(f"Entity '{name}'.relations must be an array")
        for rdef in rels_def:
            if not isinstance(rdef, dict):
                raise ValueError(f"Entity '{name}' relation must be an object")
            rtype = str(rdef.get("type", "one-to-many"))
            if rtype not in SUPPORTED_REL_TYPES:
                raise ValueError(f"Entity '{name}' relation type '{rtype}' is not supported")
            target = rdef.get("target")
            if not target:
                raise ValueError(f"Entity '{name}' relation missing target")
            rel = Relation(
                type=rtype,
                target=str(target),
                foreign_key=rdef.get("foreign_key"),
                backref=rdef.get("backref"),
                description=rdef.get("description"),
                via=rdef.get("via"),
            )
            e.relations.append(rel)
        entities[e.name] = e

    # Post-parse: ensure any FK fields declared via relations exist? Do not mutate; just for ERD markers if present
    return entities

