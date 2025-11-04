state = {
    "users": {}
}


def set_state(name: str):
    # Reset first to a clean slate
    if name in ("default", "No users", "empty"):
        state["users"].clear()
        return

    if name == "User 1 exists":
        state["users"][1] = {
            "id": 1,
            "name": "Alice"
        }
        return

    # Additional example states could be added here
    # For unknown states, just clear
    state["users"].clear()

