class SMSProvider:
    def __init__(self):
        pass

    def send(self, to_phone: str, body: str) -> bool:
        # Replace with actual SMS integration
        print(f"[SMS] To: {to_phone}\n{body}\n---")
        return True

