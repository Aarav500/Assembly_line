Auto-generate ERD and API contracts from idea entities

Quickstart
- Install: pip install -r requirements.txt
- Run server: python app.py
- Generate from sample: python generate.py

POST /generate
- Body: JSON spec with an 'entities' object. See sample/entities.json
- Returns: { erd: { mermaid, dot }, openapi: { ... } }

Spec schema
- entities: { EntityName: { description?, fields, relations? } }
- fields: { fieldName: { type, primary_key?, required?, unique?, description?, enum?, max_length?, format?, default? } }
- relations: [ { type: one-to-one|one-to-many|many-to-one|many-to-many, target, foreign_key?, backref?, description?, via? } ]

Outputs
- ERD (Mermaid): can be pasted into Mermaid-enabled viewers
- ERD (DOT): render with Graphviz (dot -Tpng build/erd.dot -o build/erd.png)
- OpenAPI 3.0 JSON for CRUD endpoints per entity

Notes
- If no primary key is provided, a default integer 'id' is added.
- Schemas include only declared fields; relation refs are not expanded to avoid cycles.

