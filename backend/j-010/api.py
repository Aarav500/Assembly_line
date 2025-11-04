from flask import Blueprint, request, jsonify, abort
from annotations import endpoint_doc

api_bp = Blueprint("api", __name__)

# In-memory store for demo purposes
USERS = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
}
_next_id = 3


@endpoint_doc(
    summary="List users",
    description="Retrieve a paginated list of users, optionally filtered by search query.",
    query={
        "page": {"type": "integer", "required": False, "default": 1, "description": "Page number (1-indexed)."},
        "per_page": {"type": "integer", "required": False, "default": 10, "description": "Items per page."},
        "search": {"type": "string", "required": False, "description": "Filter users by name or email substring."},
    },
    responses={
        200: {
            "description": "Paginated list of users",
            "body": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"type": "object"}},
                    "page": {"type": "integer"},
                    "per_page": {"type": "integer"},
                    "total": {"type": "integer"},
                },
            },
        }
    },
    tags=["Users"],
)
@api_bp.route("/users", methods=["GET"])
def list_users():
    """Retrieve a paginated list of users.

    Args:
        None: No path parameters.

    Query Parameters:
        page (int): Page number (1-indexed). Default 1
        per_page (int): Items per page. Default 10
        search (str): Search substring filter for name or email.

    Returns:
        flask.Response: JSON with items, page, per_page, total
    """
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    search = request.args.get("search")

    items = list(USERS.values())
    if search:
        s = search.lower()
        items = [u for u in items if s in u["name"].lower() or s in u["email"].lower()]
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify({"items": items[start:end], "page": page, "per_page": per_page, "total": total})


@endpoint_doc(
    summary="Get user by ID",
    description="Retrieve a single user resource by its unique ID.",
    params={"user_id": {"type": "integer", "required": True, "description": "User ID"}},
    responses={
        200: {"description": "User found", "body": {"type": "object"}},
        404: {"description": "User not found"},
    },
    tags=["Users"],
)
@api_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    """Get a user by ID.

    Args:
        user_id (int): The ID of the user.

    Returns:
        flask.Response: JSON representing the user or 404.
    """
    user = USERS.get(user_id)
    if not user:
        abort(404)
    return jsonify(user)


@endpoint_doc(
    summary="Create a user",
    description="Create a new user with a name and unique email.",
    body={
        "type": "object",
        "required": ["name", "email"],
        "properties": {
            "name": {"type": "string", "description": "Full name"},
            "email": {"type": "string", "description": "Email address"},
        },
    },
    responses={
        201: {"description": "User created", "body": {"type": "object"}},
        400: {"description": "Invalid payload"},
        409: {"description": "Email already exists"},
    },
    tags=["Users"],
)
@api_bp.route("/users", methods=["POST"])
def create_user():
    """Create a new user.

    Request Body:
        JSON object with fields name (str) and email (str).

    Returns:
        flask.Response: JSON with created user and status 201, or error status.
    """
    global _next_id
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400
    if any(u["email"].lower() == email.lower() for u in USERS.values()):
        return jsonify({"error": "email already exists"}), 409
    user = {"id": _next_id, "name": name, "email": email}
    USERS[_next_id] = user
    _next_id += 1
    return jsonify(user), 201


@endpoint_doc(
    summary="Update a user",
    description="Update user fields (partial update).",
    params={"user_id": {"type": "integer", "required": True, "description": "User ID"}},
    body={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
        },
    },
    responses={
        200: {"description": "User updated", "body": {"type": "object"}},
        400: {"description": "Invalid payload"},
        404: {"description": "Not found"},
        409: {"description": "Email already exists"},
    },
    tags=["Users"],
)
@api_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id: int):
    """Update a user.

    Args:
        user_id (int): ID of the user to update.

    Request Body:
        JSON with optional fields name (str) and/or email (str).

    Returns:
        flask.Response: JSON with updated user or error status.
    """
    user = USERS.get(user_id)
    if not user:
        abort(404)
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    if name is not None:
        user["name"] = name
    if email is not None:
        if any(u["email"].lower() == email.lower() and u["id"] != user_id for u in USERS.values()):
            return jsonify({"error": "email already exists"}), 409
        user["email"] = email
    return jsonify(user)


@endpoint_doc(
    summary="Delete a user",
    description="Delete a user by ID.",
    params={"user_id": {"type": "integer", "required": True, "description": "User ID"}},
    responses={204: {"description": "Deleted"}, 404: {"description": "Not found"}},
    tags=["Users"],
)
@api_bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id: int):
    """Delete a user by ID.

    Args:
        user_id (int): ID of the user.

    Returns:
        flask.Response: Empty response with 204 on success or 404 if not found.
    """
    user = USERS.pop(user_id, None)
    if not user:
        abort(404)
    return ("", 204)

