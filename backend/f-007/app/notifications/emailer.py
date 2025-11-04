import smtplib
from email.mime.text import MIMEText
from typing import List, Optional


class EmailNotifier:
    def __init__(self, host: Optional[str], port: int, username: Optional[str], password: Optional[str], from_email: str, use_tls: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def enabled(self) -> bool:
        return bool(self.host and self.username and self.password)

    def send(self, to_emails: List[str], subject: str, body: str) -> bool:
        if not self.enabled():
            print(f"[EmailNotifier] SMTP not configured. Would send to {to_emails}: {subject}\n{body}")
            return False
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = ", ".join(to_emails)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, to_emails, msg.as_string())
            return True
        except Exception as e:
            print(f"[EmailNotifier] Exception: {e}")
            return False

