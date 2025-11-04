from typing import Optional


class EmailProvider:
    def __init__(self):
        pass

    def send(self, to_email: str, subject: str, body: str) -> bool:
        # Replace with actual email integration
        print(f"[EMAIL] To: {to_email} | Subject: {subject}\n{body}\n---")
        return True

