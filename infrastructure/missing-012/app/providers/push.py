class PushProvider:
    def __init__(self):
        pass

    def send(self, to_token: str, title: str, body: str) -> bool:
        # Replace with actual push integration
        print(f"[PUSH] Token: {to_token} | Title: {title}\n{body}\n---")
        return True

