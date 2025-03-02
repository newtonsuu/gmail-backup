"""
Thin wrapper over the Gmail REST API.

We fetch each message in `raw` format and parse it locally with Python's
`email` module. That gives us the complete, original message (the .eml) plus
all headers/body/attachments from a single API call — no fiddling with Gmail's
per-part attachment endpoints.
"""

from __future__ import annotations

import base64
from typing import Iterator


def find_label_id(service, label_name: str) -> str | None:
    """Resolve a human label name to its Gmail label ID (case-sensitive)."""
    resp = service.users().labels().list(userId="me").execute()
    for label in resp.get("labels", []):
        if label.get("name") == label_name:
            return label["id"]
    return None


def list_label_names(service) -> list[str]:
    """All label names — handy for error messages when a label isn't found."""
    resp = service.users().labels().list(userId="me").execute()
    return sorted(label.get("name", "") for label in resp.get("labels", []))


def iter_message_ids(service, label_id: str) -> Iterator[str]:
    """Yield every message ID under a label, transparently paging the API."""
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId="me", labelIds=[label_id], maxResults=500, pageToken=page_token)
            .execute()
        )
        for msg in resp.get("messages", []):
            yield msg["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def fetch_raw(service, message_id: str) -> bytes:
    """Fetch the full raw RFC-822 bytes of a message (this *is* the .eml)."""
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="raw")
        .execute()
    )
    return base64.urlsafe_b64decode(msg["raw"].encode("ASCII"))
