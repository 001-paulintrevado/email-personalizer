"""
Gmail API client.

Handles OAuth authentication and fetching the target newsletter email.
Credentials flow:
  1. First run: opens browser for OAuth consent -> saves token.json
  2. Subsequent runs: loads token.json (refreshes automatically if expired)
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

TARGET_SENDER = "collegecounseling@lelycee.org"
TARGET_SUBJECT = "College Counseling Newsletter"

BASE_DIR = Path(__file__).parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"


def get_gmail_service():
    """Authenticate and return an authorised Gmail API service object."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_latest_newsletter(service) -> dict | None:
    """
    Search Gmail for the most recent College Counseling Newsletter.
    Returns the full message dict, or None if no matching email is found.
    """
    query = f'from:{TARGET_SENDER} subject:"{TARGET_SUBJECT}"'
    result = service.users().messages().list(userId="me", q=query, maxResults=1).execute()
    messages = result.get("messages", [])

    if not messages:
        return None

    msg_id = messages[0]["id"]
    full_msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    return full_msg


def decode_body(data: str) -> str:
    """Base64url-decode a Gmail message body part."""
    padded = data + "=" * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def extract_raw_content(message: dict) -> dict:
    """
    Pull subject, sender, date, and body text out of a raw Gmail message dict.
    Prefers plain text; falls back to HTML if plain text is absent.
    """
    headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
    subject = headers.get("Subject", "")
    sender = headers.get("From", "")
    date = headers.get("Date", "")

    plain_text = ""
    html_text = ""

    def walk_parts(parts):
        nonlocal plain_text, html_text
        for part in parts:
            mime = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")
            if mime == "text/plain" and body_data:
                plain_text += decode_body(body_data)
            elif mime == "text/html" and body_data:
                html_text += decode_body(body_data)
            if "parts" in part:
                walk_parts(part["parts"])

    payload = message["payload"]
    if "parts" in payload:
        walk_parts(payload["parts"])
    elif payload.get("body", {}).get("data"):
        body_data = payload["body"]["data"]
        if payload.get("mimeType") == "text/plain":
            plain_text = decode_body(body_data)
        else:
            html_text = decode_body(body_data)

    return {
        "subject": subject,
        "sender": sender,
        "date": date,
        "plain_text": plain_text,
        "html": html_text,
        "message_id": message["id"],
    }
