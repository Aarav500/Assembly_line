from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone

from ideater.utils import pluralize, singularize, safe_rel_name


def _derive_relationships(raw: Dict[str, Any], with_backrefs: bool) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    # key: (schema, table) -> list of relationship dicts
    rels: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for schema_name, schema in raw.get("schemas", {}).items():
        for table_name, entity in schema.get("entities", {}).items():
            if entity.get("is_view"):
                continue
            for fk in entity.get("foreign_keys", []):
                constrained = fk.get("constrained_columns", [])
                referred_table = fk.get("referred_table")
                referred_schema = fk.get("referred_schema") or schema_name
                referred_cols = fk.get("referred_columns", [])
                if not constrained or not referred_table or not referred_cols:
                    continue
                # For simple 1-column FKs, make nicer names
                if len(constrained) == 1 and len(referred_cols) == 1:
                    from_col = constrained[0]
                    to_col = referred_cols[0]
                    # many-to-one from current table to referred table
                    rel_name = safe_rel_name(table_name, from_col, referred_table)
                    rel = {
                        "name": rel_name,
                        "type": "many-to-one",
                        "from": {
                            "schema": schema_name,
                            "table": table_name,
                            "column": from_col,
                        },
                        "to": {
                            "schema": referred_schema,
                            "table": referred_table,
                            "column": to_col,
                        },
                        "fk_name": fk.get("name"),
                        "onupdate": fk.get("options", {}).get("onupdate"),
                        "ondelete": fk.get("options", {}).get("ondelete"),
                    }
                    rels.setdefault((schema_name, table_name), []).append(rel)

                    if with_backrefs:
                        back_name = pluralize(table_name)
                        back_rel = {
                            "name": back_name,
                            "type": "one-to-many",
                            "from": {
                                "schema": referred_schema,
                                "table": referred_table,
                                "column": to_col,
                            },
                            "to": {
                                "schema": schema_name,
                                "table": table_name,
                                "column": from_col,
                            },
                            "via": rel_name,
                        }
                        rels.setdefault((referred_schema, referred_table), []).append(back_rel)
                else:
                    # Composite FK
                    rel = {
                        "name": f"{singularize(referred_table)}_by_{'_and_'.join(constrained)}",
                        "type": "many-to-one",
                        "from": {
                            "schema": schema_name,
                            "table": table_name,
                            "columns": constrained,
                        },
                        "to": {
                            "schema": referred_schema,
                            "table": referred_table,
                            "columns": referred_cols,
                        },
                        "fk_name": fk.get("name"),
                        "onupdate": fk.get("options", {}).get("onupdate"),
                        "ondelete": fk.get("options", {}).get("ondelete"),
                    }
                    rels.setdefault((schema_name, table_name), []).append(rel)

                    if with_backrefs:
                        back_rel = {
                            "name": f"{pluralize(table_name)}_by_{'_and_'.join(referred_cols)}",
                            "type": "one-to-many",
                            "from": {
                                "schema": referred_schema,
                                "table": referred_table,
                                "columns": referred_cols,
                            },
                            "to": {
                                "schema": schema_name,
                                "table": table_name,
                                "columns": constrained,
                            },
                            "via": rel.get("name"),
                        }
                        rels.setdefault((referred_schema, referred_table), []).append(back_rel)

    return rels


def build_entity_mapping(raw: Dict[str, Any], masked_db_url: str, with_backrefs: bool = True) -> Dict[str, Any]:
    relationships = _derive_relationships(raw, with_backrefs)

    mapping: Dict[str, Any] = {
        "format": "ideater-entity-mapping-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": {
            "dialect": raw.get("dialect"),
            "driver": raw.get("driver"),
            "server_version": raw.get("server_version"),
            "url": masked_db_url,
        },
        "schemas": [],
    }

    for schema_name, schema in raw.get("schemas", {}).items():
        schema_node: Dict[str, Any] = {"name": schema_name, "entities": []}
        for table_name, ent in schema.get("entities", {}).items():
            entity_node: Dict[str, Any] = {
                "name": table_name,
                "qualified_name": f"{schema_name}.{table_name}",
                "is_view": ent.get("is_view", False),
                "columns": ent.get("columns", []),
                "primary_key": ent.get("primary_key", {}),
                "foreign_keys": ent.get("foreign_keys", []),
                "unique_constraints": ent.get("unique_constraints", []),
                "indexes": ent.get("indexes", []),
                "comment": ent.get("comment"),
                "relationships": relationships.get((schema_name, table_name), []),
            }
            schema_node["entities"].append(entity_node)
        mapping["schemas"].append(schema_node)

    return mapping

