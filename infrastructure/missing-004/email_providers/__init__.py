from typing import Protocol, Tuple, Optional, List, Dict


class EmailProvider(Protocol):
    def send(
        self,
        *,
        to_email: str,
        from_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        email_id: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """
        Sends an email
        Returns: (message_id, provider_response)
        """
        ...

