from typing import Dict
from .utils import Entity, Field, map_field_to_mermaid_type, cardinality_symbols, get_primary_key_field


def _field_markers(f: Field) -> str:
    marks = []
    if f.primary_key:
        marks.append("PK")
    if f.unique and not f.primary_key:
        marks.append("UK")
    return " ".join(marks)


def generate_mermaid_erd(entities: Dict[str, Entity]) -> str:
    lines = ["erDiagram"]
    # Entities with attributes
    for name, ent in entities.items():
        lines.append(f"  {name} {{")
        # Ensure PK exists
        _ = get_primary_key_field(ent)
        for fname, f in ent.fields.items():
            t = map_field_to_mermaid_type(f)
            marks = _field_markers(f)
            if marks:
                lines.append(f"    {t} {fname} {marks}")
            else:
                lines.append(f"    {t} {fname}")
        lines.append("  }")
    # Relationships
    for name, ent in entities.items():
        for rel in ent.relations:
            left, right = cardinality_symbols(rel.type)
            label = rel.type
            lines.append(f"  {name} {left}--{right} {rel.target} : {label}")
    return "\n".join(lines)


def generate_dot_erd(entities: Dict[str, Entity]) -> str:
    lines = [
        "digraph ERD {",
        "  graph [rankdir=LR];",
        "  node [shape=record, fontname=Helvetica];",
        "  edge [arrowhead=none, fontname=Helvetica];",
    ]
    # Nodes
    for name, ent in entities.items():
        fields_parts = []
        # Ensure PK exists
        _ = get_primary_key_field(ent)
        for fname, f in ent.fields.items():
            marks = []
            if f.primary_key:
                marks.append("PK")
            if f.unique and not f.primary_key:
                marks.append("UK")
            label = f"{fname}: {f.type}"
            if marks:
                label += f" ({', '.join(marks)})"
            fields_parts.append(label)
        fields_label = "\\l".join(fields_parts) + "\\l" if fields_parts else ""
        node_label = f"{{{name}|{fields_label}}}"
        lines.append(f"  {name} [label=\"{node_label}\"];")
    # Edges - we will annotate with relationship type, and stylize cardinality ends with crow's-foot using labels
    for name, ent in entities.items():
        for rel in ent.relations:
            # Simple line with label; DOT doesn't natively support crow's-foot w/o custom markers
            lines.append(f"  {name} -> {rel.target} [label=\"{rel.type}\", arrowhead=none];")
    lines.append("}")
    return "\n".join(lines)

