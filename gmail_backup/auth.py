"""
Google OAuth + Gmail service.

Gmail access is requested **read-only** — this tool can never modify or delete
your mail. On first run a browser window opens for you to grant access; the
resulting token is cached in token.json so you won't be prompted again.
"""

from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import Config

# Read-only on purpose. If you change this, delete token.json to re-consent.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_service(cfg: Config):
    """Return an authorized Gmail API service, running the OAuth flow if needed."""
    creds: Credentials | None = None

    if cfg.token_file.exists():
        creds = Credentials.from_authorized_user_file(str(cfg.token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not cfg.credentials_file.exists():
                raise FileNotFoundError(
                    f"Missing OAuth client file: {cfg.credentials_file}\n"
                    "Download it from Google Cloud Console (see README, step 'Get "
                    "credentials.json') and place it next to main.py."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(cfg.credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)
        cfg.token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)
