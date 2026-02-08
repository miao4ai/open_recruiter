"""Email sending tool — supports console (default), SendGrid, and Gmail."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel

from open_recruiter.config import Config
from open_recruiter.schemas import Email

console = Console()


def send_email(config: Config, email: Email) -> bool:
    """Send an email using the configured backend. Returns True on success."""
    backend = config.email_backend.lower()

    if backend == "sendgrid":
        return _send_sendgrid(config, email)
    elif backend == "gmail":
        return _send_gmail(config, email)
    else:
        return _send_console(email)


def _send_console(email: Email) -> bool:
    """Print email to the console (default MVP mode)."""
    console.print(Panel(
        f"[bold]To:[/bold] {email.to}\n"
        f"[bold]Subject:[/bold] {email.subject}\n"
        f"[bold]Type:[/bold] {email.email_type}\n\n"
        f"{email.body}",
        title="📧 Email (Console Mode)",
        border_style="cyan",
    ))
    email.sent = True
    email.sent_at = datetime.now()
    return True


def _send_sendgrid(config: Config, email: Email) -> bool:
    """Send via SendGrid API."""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Content, Mail, To

        sg = sendgrid.SendGridAPIClient(api_key=config.sendgrid_api_key)
        message = Mail(
            from_email=config.email_from,
            to_emails=To(email.to),
            subject=email.subject,
            plain_text_content=Content("text/plain", email.body),
        )
        response = sg.client.mail.send.post(request_body=message.get())
        if response.status_code in (200, 201, 202):
            email.sent = True
            email.sent_at = datetime.now()
            return True
        console.print(f"[red]SendGrid error: {response.status_code}[/red]")
        return False
    except ImportError:
        console.print("[red]sendgrid package not installed. Run: pip install sendgrid[/red]")
        return False
    except Exception as e:
        console.print(f"[red]SendGrid error: {e}[/red]")
        return False


def _send_gmail(config: Config, email: Email) -> bool:
    """Send via Gmail API (placeholder — requires OAuth setup)."""
    console.print("[yellow]Gmail integration requires OAuth setup. Falling back to console mode.[/yellow]")
    return _send_console(email)
