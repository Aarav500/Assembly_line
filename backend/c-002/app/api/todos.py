from flask import Blueprint, jsonify, make_response, request

bp = Blueprint("todos", __name__)

# In-memory storage for todos
_todos = {}
_next_id = 1


@bp.get("/")
def list_todos():
    return jsonify(list(_todos.values())), 200


@bp.post("/")
def create_todo():
    global _next_id
    data = request.get_json()
    
    # Validation
    if not data or "title" not in data:
        return make_response(
            jsonify({
                "error": "validation_error",
                "details": "title is required"
            }),
            400,
        )
    
    # Create todo
    todo = {
        "id": _next_id,
        "title": data["title"],
        "completed": data.get("completed", False),
        "due_date": data.get("due_date")
    }
    _todos[_next_id] = todo
    _next_id += 1
    
    return jsonify(todo), 201


@bp.get("/<int:todo_id>")
def get_todo(todo_id: int):
    todo = _todos.get(todo_id)
    if not todo:
        return make_response(
            jsonify({"error": "not_found"}),
            404,
        )
    return jsonify(todo), 200


@bp.put("/<int:todo_id>")
def update_todo(todo_id: int):
    if todo_id not in _todos:
        return make_response(
            jsonify({"error": "not_found"}),
            404,
        )
    
    data = request.get_json()
    
    # Validation
    if not data or "title" not in data:
        return make_response(
            jsonify({
                "error": "validation_error",
                "details": "title is required"
            }),
            400,
        )
    
    # Update todo
    todo = _todos[todo_id]
    todo["title"] = data["title"]
    todo["completed"] = data.get("completed", todo["completed"])
    if "due_date" in data:
        todo["due_date"] = data["due_date"]
    
    return jsonify(todo), 200


@bp.delete("/<int:todo_id>")
def delete_todo(todo_id: int):
    if todo_id not in _todos:
        return make_response(
            jsonify({"error": "not_found"}),
            404,
        )
    
    del _todos[todo_id]
    return make_response("", 204)
