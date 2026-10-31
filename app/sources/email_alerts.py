"""Authorized IMAP alert ingestion for LinkedIn, Indeed, StepStone, and XING."""

from __future__ import annotations

import email
import imaplib
import re

from . import JobRecord, strip_html


def parse_alert_message(raw: bytes, source_hint: str = "email_alert") -> JobRecord | None:
    msg = email.message_from_bytes(raw)
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in {"text/plain", "text/html"}:
                body_parts.append((part.get_payload(decode=True) or b"").decode(errors="ignore"))
    else:
        body_parts.append((msg.get_payload(decode=True) or b"").decode(errors="ignore"))
    body = strip_html(" ".join(body_parts))
    links = re.findall(r"https?://[^\s<>\"]+", body)
    if not links:
        return None
    subject = msg.get("Subject", "Job alert")
    source = source_hint
    sender = (msg.get("From") or "").lower()
    for name in ("linkedin", "indeed", "stepstone", "xing"):
        if name in sender or name in subject.lower():
            source = name
            break
    title = subject.replace("Job alert:", "").replace("Jobs you may be interested in", "").strip()
    return JobRecord(
        title or "Job alert", source.title(), "", links[0], "", source, source_links=[links[0]]
    )


def test_connection(host: str, username: str, password: str, port: int = 993) -> tuple[bool, str]:
    if not all((host, username, password)):
        return False, "IMAP host, username, and password are required"
    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(username, password)
        mail.logout()
        return True, "IMAP connection successful"
    except (OSError, imaplib.IMAP4.error) as exc:
        return False, f"IMAP connection failed: {exc}"


def fetch_alerts(
    host: str, username: str, password: str, folder: str = "INBOX", port: int = 993
) -> list[JobRecord]:
    if not all((host, username, password)):
        return []
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(username, password)
    mail.select(folder)
    _, data = mail.search(None, "UNSEEN")
    records = []
    for num in data[0].split():
        _, raw = mail.fetch(num, "(RFC822)")
        record = parse_alert_message(raw[0][1])
        if record:
            records.append(record)
    mail.logout()
    return records
