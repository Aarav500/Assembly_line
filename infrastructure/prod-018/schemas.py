from marshmallow import Schema, fields


class UserSchema(Schema):
    id = fields.Int(dump_only=True, metadata={"description": "Unique user identifier"}, example=1)
    name = fields.Str(required=True, metadata={"description": "Full name"}, example="Alice")
    email = fields.Email(required=True, metadata={"description": "Email address"}, example="alice@example.com")
    created_at = fields.DateTime(dump_only=True, metadata={"description": "Creation timestamp (UTC)"}, example="2025-01-01T12:00:00+00:00")


class UserCreateSchema(Schema):
    name = fields.Str(required=True, metadata={"description": "Full name"}, example="Charlie")
    email = fields.Email(required=True, metadata={"description": "Email address"}, example="charlie@example.com")


class UserUpdateSchema(Schema):
    name = fields.Str(required=False, metadata={"description": "Full name"}, example="Updated Name")
    email = fields.Email(required=False, metadata={"description": "Email address"}, example="updated@example.com")


class ListQueryArgsSchema(Schema):
    limit = fields.Int(load_default=10, metadata={"description": "Max results to return"}, example=10)
    offset = fields.Int(load_default=0, metadata={"description": "Number of items to skip"}, example=0)
    search = fields.Str(load_default=None, allow_none=True, metadata={"description": "Search by name or email (case-insensitive substring)"}, example="ali")

