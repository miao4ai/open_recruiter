"""Email sending tool — supports console (dev) and SMTP/Gmail."""

from __future__ import annotations

import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def send_email(
    *,
    backend: str,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_username: str = "",
    smtp_password: str = "",
    attachment_path: str = "",
) -> dict:
    """Send an email using the configured backend.

    Returns {"status": "ok"} on success or {"status": "error", "message": ...}.
    """
    if backend == "console":
        import uuid as _uuid
        fake_mid = f"<{_uuid.uuid4().hex}@open-recruiter.local>"
        print(f"\n{'='*60}")
        print(f"  EMAIL (console mode — not actually sent)")
        print(f"  From: {from_email}")
        print(f"  To:   {to_email}")
        print(f"  Subject: {subject}")
        print(f"  Message-ID: {fake_mid}")
        if attachment_path:
            print(f"  Attachment: {attachment_path}")
        print(f"{'='*60}")
        print(body)
        print(f"{'='*60}\n")
        return {"status": "ok", "message": "Printed to console (dev mode)", "message_id": fake_mid}

    if backend in ("smtp", "gmail"):
        # Auto-fill Gmail SMTP settings
        if backend == "gmail":
            smtp_host = smtp_host or "smtp.gmail.com"
            smtp_port = smtp_port or 587
            smtp_username = smtp_username or from_email

        if not smtp_host:
            return {"status": "error", "message": "SMTP host not configured"}
        if not smtp_password:
            return {"status": "error", "message": "SMTP password not configured (for Gmail, use an App Password)"}

        try:
            # Use "mixed" when there's an attachment, "alternative" otherwise
            msg = MIMEMultipart("mixed" if attachment_path else "alternative")
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # Attach file if provided
            if attachment_path:
                file_path = Path(attachment_path)
                if file_path.exists():
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(file_path.read_bytes())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{file_path.name}"',
                    )
                    msg.attach(part)

            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_username or from_email, smtp_password)
                server.sendmail(from_email, [to_email], msg.as_string())

            # Capture Message-ID for reply matching
            message_id = msg["Message-ID"] or ""
            return {"status": "ok", "message": "Email sent via SMTP", "message_id": message_id}
        except smtplib.SMTPAuthenticationError:
            return {"status": "error", "message": "SMTP authentication failed. For Gmail, use an App Password (not your regular password)."}
        except Exception as e:
            return {"status": "error", "message": f"SMTP error: {e}"}

    return {"status": "error", "message": f"Unknown email backend: {backend}"}
