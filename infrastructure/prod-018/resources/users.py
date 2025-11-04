from flask.views import MethodView
from flask_smorest import Blueprint, abort
from datetime import datetime, timezone

from schemas import (
    UserSchema,
    UserCreateSchema,
    UserUpdateSchema,
    ListQueryArgsSchema,
)
from storage import USERS, next_id


blp = Blueprint(
    "Users",
    __name__,
    description="Operations on users with automatic OpenAPI/Swagger documentation",
)


@blp.route("/users")
class UsersList(MethodView):
    @blp.doc(
        summary="List users",
        description="Returns a paginated list of users. Supports simple text search across name and email.",
        operationId="listUsers",
    )
    @blp.arguments(ListQueryArgsSchema, location="query")
    @blp.response(
        200,
        UserSchema(many=True),
        example=[
            {
                "id": 1,
                "name": "Alice",
                "email": "alice@example.com",
                "created_at": "2025-01-01T12:00:00+00:00",
            }
        ],
    )
    def get(self, args):
        limit = args.get("limit", 10)
        offset = args.get("offset", 0)
        search = (args.get("search") or "").lower().strip()

        all_users = list(USERS.values())

        if search:
            all_users = [
                u
                for u in all_users
                if search in u["name"].lower() or search in u["email"].lower()
            ]

        # simple pagination slice
        items = all_users[offset : offset + limit]
        return items

    @blp.doc(
        summary="Create a user",
        description="Creates a new user. Email must be unique.",
        operationId="createUser",
    )
    @blp.arguments(UserCreateSchema)
    @blp.response(
        201,
        UserSchema,
        example={
            "id": 3,
            "name": "Charlie",
            "email": "charlie@example.com",
            "created_at": "2025-01-02T15:30:00+00:00",
        },
    )
    def post(self, new_user):
        # Uniqueness check for email
        for u in USERS.values():
            if u["email"].lower() == new_user["email"].lower():
                abort(409, message="Email already exists")

        uid = next_id()
        user = {
            "id": uid,
            "name": new_user["name"],
            "email": new_user["email"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        USERS[uid] = user
        return user


@blp.route("/users/<int:user_id>")
class UserDetail(MethodView):
    @blp.doc(
        summary="Get a user",
        description="Returns a single user by ID.",
        operationId="getUser",
    )
    @blp.response(
        200,
        UserSchema,
        example={
            "id": 1,
            "name": "Alice",
            "email": "alice@example.com",
            "created_at": "2025-01-01T12:00:00+00:00",
        },
    )
    def get(self, user_id: int):
        user = USERS.get(user_id)
        if not user:
            abort(404, message="User not found")
        return user

    @blp.doc(
        summary="Update a user",
        description="Partially updates a user. Only provided fields are updated.",
        operationId="updateUser",
    )
    @blp.arguments(UserUpdateSchema)
    @blp.response(
        200,
        UserSchema,
        example={
            "id": 1,
            "name": "Alice Updated",
            "email": "alice.updated@example.com",
            "created_at": "2025-01-01T12:00:00+00:00",
        },
    )
    def patch(self, update_data, user_id: int):
        user = USERS.get(user_id)
        if not user:
            abort(404, message="User not found")

        # If email is updated, ensure uniqueness
        new_email = update_data.get("email")
        if new_email and new_email.lower() != user["email"].lower():
            for uid, u in USERS.items():
                if uid != user_id and u["email"].lower() == new_email.lower():
                    abort(409, message="Email already exists")

        user.update({k: v for k, v in update_data.items() if v is not None})
        return user

    @blp.doc(
        summary="Delete a user",
        description="Deletes a user by ID.",
        operationId="deleteUser",
    )
    def delete(self, user_id: int):
        if user_id not in USERS:
            abort(404, message="User not found")
        del USERS[user_id]
        return "", 204

