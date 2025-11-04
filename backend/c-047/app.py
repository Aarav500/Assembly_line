import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the Flask class from the flask module
# Flask is the core framework for building web applications
from flask import Flask, jsonify, request

# Create an instance of the Flask class
# __name__ helps Flask determine the root path of the application
app = Flask(__name__)

# In-memory data store for demo purposes
# In production, you would use a proper database
items = []


# Define the root route using the @app.route decorator
# This responds to HTTP GET requests at '/'
@app.route('/')
def home():
    """Home endpoint that returns a welcome message."""
    # Return a simple JSON response with a welcome message
    return jsonify({"message": "Welcome to the Flask API"})


# Define an endpoint to retrieve all items
# methods=['GET'] explicitly specifies this route only accepts GET requests
@app.route('/items', methods=['GET'])
def get_items():
    """Get all items from the in-memory store."""
    # jsonify converts Python dictionaries/lists to JSON format
    return jsonify({"items": items}), 200


# Define an endpoint to add a new item
# methods=['POST'] means this route accepts POST requests for creating resources
@app.route('/items', methods=['POST'])
def add_item():
    """Add a new item to the store."""
    # request.get_json() extracts JSON data from the incoming request body
    data = request.get_json()
    
    # Validate that the request contains a 'name' field
    if not data or 'name' not in data:
        # Return error response with 400 (Bad Request) status code
        return jsonify({"error": "Name is required"}), 400
    
    # Create a new item with an auto-incremented ID
    # The ID is based on the current length of the items list
    item = {
        "id": len(items) + 1,
        "name": data['name']
    }
    
    # Append the new item to our in-memory list
    items.append(item)
    
    # Return the created item with 201 (Created) status code
    return jsonify(item), 201


# Define an endpoint to retrieve a specific item by ID
# <int:item_id> is a URL parameter that captures an integer value
@app.route('/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    """Get a specific item by its ID."""
    # Use next() with a generator expression to find the item
    # This is more efficient than iterating through the entire list
    item = next((item for item in items if item['id'] == item_id), None)
    
    # If item is not found, return 404 (Not Found) error
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    
    # Return the found item with 200 (OK) status code
    return jsonify(item), 200


# This conditional ensures the app only runs when executed directly
# It won't run if this file is imported as a module in another script
if __name__ == '__main__':
    # Start the Flask development server
    # debug=True enables auto-reload and detailed error messages
    # WARNING: Never use debug=True in production!
    app.run(debug=True)



def create_app():
    return app
