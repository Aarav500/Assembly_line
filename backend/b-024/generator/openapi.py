from typing import Dict, List
from .utils import Entity, Field, map_field_to_jsonschema, pluralize, get_primary_key_field


def _entity_schema(ent: Entity) -> Dict:
    properties: Dict[str, Dict] = {}
    required: List[str] = []
    for fname, f in ent.fields.items():
        properties[fname] = map_field_to_jsonschema(f)
        if f.required or f.primary_key:
            required.append(fname)
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    if ent.description:
        schema["description"] = ent.description
    return schema


def _request_body_for(ent: Entity, method: str) -> Dict:
    schema = _entity_schema(ent)
    if method.lower() == "post":
        # Generally exclude primary key from required on POST if default PK
        pk = get_primary_key_field(ent)
        if "required" in schema and pk.name in schema["required"]:
            req = [r for r in schema["required"] if r != pk.name]
            if req:
                schema["required"] = req
            else:
                schema.pop("required", None)
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": schema
            }
        }
    }


def generate_openapi(entities: Dict[str, Entity], title: str = "Idea Entities API", version: str = "1.0.0", base_path: str = "/api") -> Dict:
    components = {"schemas": {}}
    paths: Dict[str, Dict] = {}

    for name, ent in entities.items():
        schema_name = name
        components["schemas"][schema_name] = _entity_schema(ent)
        coll = pluralize(name).lower()
        pk_field = get_primary_key_field(ent)
        pk_schema = map_field_to_jsonschema(pk_field)

        list_path = f"{base_path}/{coll}"
        item_path = f"{base_path}/{coll}/{{{pk_field.name}}}"

        # GET collection
        paths[list_path] = paths.get(list_path, {})
        paths[list_path]["get"] = {
            "summary": f"List {coll}",
            "operationId": f"list{coll.capitalize()}",
            "responses": {
                "200": {
                    "description": "A list of items",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": f"#/components/schemas/{schema_name}"}
                            }
                        }
                    }
                }
            }
        }
        # POST create
        paths[list_path]["post"] = {
            "summary": f"Create {name}",
            "operationId": f"create{name}",
            "requestBody": _request_body_for(ent, "post"),
            "responses": {
                "201": {
                    "description": "Created",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                        }
                    }
                }
            }
        }

        # Item endpoints
        paths[item_path] = paths.get(item_path, {})
        param = {
            "name": pk_field.name,
            "in": "path",
            "required": True,
            "schema": pk_schema
        }

        # GET by id
        paths[item_path]["get"] = {
            "summary": f"Get {name} by {pk_field.name}",
            "operationId": f"get{name}",
            "parameters": [param],
            "responses": {
                "200": {
                    "description": "OK",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                        }
                    }
                },
                "404": {"description": "Not Found"}
            }
        }
        # PUT replace
        paths[item_path]["put"] = {
            "summary": f"Replace {name}",
            "operationId": f"replace{name}",
            "parameters": [param],
            "requestBody": _request_body_for(ent, "put"),
            "responses": {
                "200": {
                    "description": "OK",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                        }
                    }
                }
            }
        }
        # PATCH update
        paths[item_path]["patch"] = {
            "summary": f"Update {name}",
            "operationId": f"update{name}",
            "parameters": [param],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": components["schemas"][schema_name]["properties"],
                        }
                    }
                }
            },
            "responses": {
                "200": {
                    "description": "OK",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                        }
                    }
                }
            }
        }
        # DELETE
        paths[item_path]["delete"] = {
            "summary": f"Delete {name}",
            "operationId": f"delete{name}",
            "parameters": [param],
            "responses": {
                "204": {"description": "No Content"}
            }
        }

    openapi = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": version,
        },
        "servers": [{"url": "/"}],
        "paths": paths,
        "components": components,
    }
    return openapi

