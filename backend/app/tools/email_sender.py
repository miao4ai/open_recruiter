"""Email sending tool — supports console (dev) and SMTP/Gmail."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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
) -> dict:
    """Send an email using the configured backend.

    Returns {"status": "ok"} on success or {"status": "error", "message": ...}.
    """
    if backend == "console":
        print(f"\n{'='*60}")
        print(f"  EMAIL (console mode — not actually sent)")
        print(f"  From: {from_email}")
        print(f"  To:   {to_email}")
        print(f"  Subject: {subject}")
        print(f"{'='*60}")
        print(body)
        print(f"{'='*60}\n")
        return {"status": "ok", "message": "Printed to console (dev mode)"}

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
            msg = MIMEMultipart("alternative")
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_username or from_email, smtp_password)
                server.sendmail(from_email, [to_email], msg.as_string())

            return {"status": "ok", "message": "Email sent via SMTP"}
        except smtplib.SMTPAuthenticationError:
            return {"status": "error", "message": "SMTP authentication failed. For Gmail, use an App Password (not your regular password)."}
        except Exception as e:
            return {"status": "error", "message": f"SMTP error: {e}"}

    return {"status": "error", "message": f"Unknown email backend: {backend}"}
