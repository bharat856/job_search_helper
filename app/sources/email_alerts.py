"""Optional authorized IMAP alert adapter; it never represents direct LinkedIn/Indeed APIs."""

import email
import imaplib
import re

from . import JobRecord


def fetch_alerts(host: str, username: str, password: str, folder: str = "INBOX") -> list[JobRecord]:
    if not all((host, username, password)):
        return []
    mail = imaplib.IMAP4_SSL(host)
    mail.login(username, password)
    mail.select(folder)
    _, data = mail.search(None, "UNSEEN")
    records = []
    for num in data[0].split():
        _, raw = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(raw[0][1])
        body = msg.get_payload(decode=True) or b""
        text = body.decode(errors="ignore")
        links = re.findall(r"https?://[^\s<>\"]+", text)
        if links:
            records.append(
                JobRecord(
                    msg.get("Subject", "Job alert"), "Email alert", "", links[0], "", "email_alert"
                )
            )
    mail.logout()
    return records
