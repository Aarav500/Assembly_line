from flask import Flask, jsonify, request, Response


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing

    @app.get("/")
    def index():
        return jsonify(message="Welcome", app="test-gen")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/echo")
    def echo():
        data = request.get_json(silent=True) or {}
        return jsonify(echo=data, received=True), 200

    @app.get("/greet/<name>")
    def greet(name: str):
        return jsonify(greeting=f"Hello, {name}!")

    @app.get("/items")
    def items():
        try:
            limit = int(request.args.get("limit", "3"))
        except ValueError:
            limit = 3
        items = [{"id": i, "name": f"Item {i}"} for i in range(1, limit + 1)]
        return jsonify(items=items, count=len(items))

    @app.get("/todo")
    def todo():
        html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Todo App</title>
</head>
<body>
  <h1 id="title">Todo</h1>
  <input id="add-todo-input" placeholder="New todo"/>
  <button id="add-todo-btn">Add</button>
  <ul id="todo-list"></ul>
  <script>
    const input = document.getElementById('add-todo-input');
    const btn = document.getElementById('add-todo-btn');
    const list = document.getElementById('todo-list');
    btn.addEventListener('click', () => {
      const text = input.value.trim();
      if (!text) return;
      const li = document.createElement('li');
      li.textContent = text;
      li.setAttribute('data-testid', 'todo-item');
      list.appendChild(li);
      input.value = '';
    });
  </script>
</body>
</html>
"""
        return Response(html, mimetype="text/html")

    return app

