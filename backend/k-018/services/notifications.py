import smtplib
from email.message import EmailMessage


class NotificationService:
    def __init__(self, config):
        self.smtp_host = config.get('SMTP_HOST')
        self.smtp_port = int(config.get('SMTP_PORT') or 587)
        self.smtp_user = config.get('SMTP_USER')
        self.smtp_pass = config.get('SMTP_PASS')
        self.smtp_from = config.get('SMTP_FROM') or (self.smtp_user or 'no-reply@example.com')
        self.enabled = bool(self.smtp_host)

    def send_request_email(self, to_email: str, to_name: str, req, approve_url: str, bundle_url: str):
        subject = f"Action required: {req.title}"
        body = f"""
Hello {to_name},

An audit approval has been requested.

Title: {req.title}
Description: {req.description or '-'}
Status: {req.status}

Bundle: {bundle_url}
Approve/Reject: {approve_url}

Thank you.
"""
        if not self.enabled:
            print("[NotificationService] SMTP not configured. Would send email:")
            print(f"To: {to_email}\nSubject: {subject}\n\n{body}")
            return
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.smtp_from
        msg['To'] = to_email
        msg.set_content(body)
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            if self.smtp_user:
                server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)

