import os
from typing import Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive'
]

_docs_service = None


def _get_docs_service(service_account_file: str):
    global _docs_service
    if _docs_service is not None:
        return _docs_service
    if not service_account_file or not os.path.isfile(service_account_file):
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is not configured or file not found")
    creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
    _docs_service = build('docs', 'v1', credentials=creds, cache_discovery=False)
    return _docs_service


def export_to_google_docs(title: str, content: str, options: Dict[str, Any], settings) -> Dict[str, Any]:
    docs_service = _get_docs_service(settings.GOOGLE_SERVICE_ACCOUNT_FILE)

    doc = docs_service.documents().create(body={"title": title or 'Untitled'}).execute()
    doc_id = doc.get('documentId')

    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": content or ''
            }
        }
    ]

    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    return {
        "id": doc_id,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit"
    }

