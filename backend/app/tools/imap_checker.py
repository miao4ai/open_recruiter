"""IMAP reply detection — connects to inbox and matches replies to sent emails."""

from __future__ import annotations

import email
import imaplib
import logging
import re
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parseaddr

from app import database as db
from app.config import Config

log = logging.getLogger(__name__)


def _decode_header_value(value: str | None) -> str:
    """Decode an email header that might be RFC2047-encoded."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return "".join(decoded)


def _extract_plain_text(msg: email.message.Message) -> str:
    """Extract plain text body from a MIME message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and part.get("Content-Disposition") != "attachment":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


def _normalize_subject(subject: str) -> str:
    """Strip Re:/Fwd:/etc. prefixes for matching."""
    return re.sub(r"^(Re|Fwd|Fw|回复|转发)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()


def check_replies(cfg: Config) -> list[dict]:
    """Connect to IMAP inbox and find replies to our sent emails.

    Returns a list of dicts: {email_id, reply_body, replied_at, from_email}
    """
    # Get sent emails that haven't been replied to
    unreplied = db.list_sent_unreplied_emails()
    if not unreplied:
        log.info("No unreplied sent emails to check.")
        return []

    # Build lookup structures
    # 1. By Message-ID for In-Reply-To matching
    by_message_id: dict[str, dict] = {}
    for e in unreplied:
        mid = e.get("message_id", "")
        if mid:
            by_message_id[mid] = e

    # 2. By (normalized_subject, to_email) for subject+sender matching
    by_subject_sender: dict[tuple[str, str], dict] = {}
    for e in unreplied:
        subj = _normalize_subject(e.get("subject", ""))
        to_addr = (e.get("to_email") or "").lower()
        if subj and to_addr:
            by_subject_sender[(subj.lower(), to_addr)] = e

    # Connect to IMAP
    imap_host = cfg.imap_host
    imap_port = cfg.imap_port
    imap_user = cfg.imap_username or cfg.smtp_username or cfg.email_from
    imap_pass = cfg.imap_password or cfg.smtp_password

    log.info("Connecting to IMAP %s:%d as %s", imap_host, imap_port, imap_user)

    try:
        if imap_port == 993:
            conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        else:
            conn = imaplib.IMAP4(imap_host, imap_port)
            conn.starttls()
        conn.login(imap_user, imap_pass)
    except Exception as e:
        log.error("IMAP connection failed: %s", e)
        raise

    try:
        conn.select("INBOX", readonly=True)

        # Search for recent emails (last 7 days)
        since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        _, msg_nums = conn.search(None, f'(SINCE {since})')
        if not msg_nums or not msg_nums[0]:
            log.info("No recent emails in INBOX.")
            return []

        msg_ids = msg_nums[0].split()
        log.info("Checking %d recent inbox messages for replies.", len(msg_ids))

        matches: list[dict] = []
        matched_email_ids: set[str] = set()

        for num in msg_ids:
            _, data = conn.fetch(num, "(RFC822)")
            if not data or not data[0] or not isinstance(data[0], tuple):
                continue

            msg = email.message_from_bytes(data[0][1])

            # Try matching by In-Reply-To or References headers
            in_reply_to = msg.get("In-Reply-To", "").strip()
            references = msg.get("References", "").strip()
            matched_email = None

            if in_reply_to and in_reply_to in by_message_id:
                matched_email = by_message_id[in_reply_to]
            elif references:
                for ref in references.split():
                    ref = ref.strip()
                    if ref in by_message_id:
                        matched_email = by_message_id[ref]
                        break

            # Fallback: match by subject + sender
            if not matched_email:
                subj = _normalize_subject(_decode_header_value(msg.get("Subject", "")))
                _, from_addr = parseaddr(msg.get("From", ""))
                from_addr = from_addr.lower()
                key = (subj.lower(), from_addr)
                if key in by_subject_sender:
                    matched_email = by_subject_sender[key]

            if matched_email and matched_email["id"] not in matched_email_ids:
                matched_email_ids.add(matched_email["id"])
                reply_body = _extract_plain_text(msg)
                date_str = msg.get("Date", "")
                try:
                    from email.utils import parsedate_to_datetime
                    replied_at = parsedate_to_datetime(date_str).isoformat()
                except Exception:
                    replied_at = datetime.now().isoformat()

                _, from_addr = parseaddr(msg.get("From", ""))
                matches.append({
                    "email_id": matched_email["id"],
                    "reply_body": reply_body[:5000],  # Limit stored size
                    "replied_at": replied_at,
                    "from_email": from_addr,
                })

        log.info("Found %d replies.", len(matches))
        return matches

    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass
