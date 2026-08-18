"""OAuth 2.0 for the YouTube Data API v3.

Uses the installed-app flow once (opens a browser / prints a URL) and then
caches the refresh token on disk so every subsequent upload is
non-interactive -- required for this to run unattended on a schedule.
"""
from __future__ import annotations

from pathlib import Path

from ..exceptions import ConfigurationError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_credentials(client_secrets_file: str | None, token_file: str):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:  # pragma: no cover
        raise ConfigurationError(
            "pip install google-api-python-client google-auth-oauthlib to use the uploader"
        ) from exc

    token_path = Path(token_file)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not client_secrets_file:
            raise ConfigurationError(
                "YOUTUBE_CLIENT_SECRETS_FILE is not set. Download an OAuth "
                "client secret JSON from Google Cloud Console and set its "
                "path in .env."
            )
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return creds
