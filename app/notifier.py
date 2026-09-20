"""Email notifications for completed document processing."""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable

from dotenv import load_dotenv

from app.status import ProcessingDecision, ProcessingStatus
from app.validator import Invoice


class NotificationError(RuntimeError):
    """Raised when notification configuration or delivery fails."""


@dataclass(frozen=True)
class EmailNotificationConfig:
    """SMTP settings; Gmail may reuse the stage 12 app credentials."""

    host: str
    port: int
    username: str
    password: str
    recipient: str
    sender: str

    @classmethod
    def from_env(cls) -> "EmailNotificationConfig | None":
        load_dotenv()
        username = os.getenv("SMTP_USERNAME") or os.getenv("IMAP_USERNAME")
        password = os.getenv("SMTP_PASSWORD") or os.getenv("IMAP_PASSWORD")
        recipient = os.getenv("NOTIFICATION_EMAIL_TO") or username
        if not any((username, password, recipient)):
            return None
        missing = [
            name
            for name, value in (
                ("SMTP_USERNAME/IMAP_USERNAME", username),
                ("SMTP_PASSWORD/IMAP_PASSWORD", password),
                ("NOTIFICATION_EMAIL_TO", recipient),
            )
            if not value
        ]
        if missing:
            raise NotificationError(
                "Missing email notification settings: " + ", ".join(missing)
            )
        try:
            port = int(os.getenv("SMTP_PORT", "465"))
        except ValueError as error:
            raise NotificationError("SMTP_PORT must be an integer") from error
        return cls(
            host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            port=port,
            username=username or "",
            password=password or "",
            recipient=recipient or "",
            sender=os.getenv("SMTP_FROM") or username or "",
        )


def build_notification(
    invoice: Invoice, decision: ProcessingDecision
) -> EmailMessage:
    """Build a compact business notification for an invoice decision."""

    message = EmailMessage()
    if decision.status == ProcessingStatus.PROCESSED:
        message["Subject"] = f"Invoice {invoice.invoice_number} processed successfully"
        headline = "Invoice processed successfully."
    else:
        message["Subject"] = f"Invoice {invoice.invoice_number} requires review"
        headline = "Document requires manual review."

    lines = [
        headline,
        "",
        f"Invoice: {invoice.invoice_number}",
        f"Company: {invoice.company_name}",
        f"Total: {invoice.total:.2f} {invoice.currency}",
        f"Status: {decision.status.value}",
    ]
    if decision.reasons:
        lines.extend(("", "Reasons:", *(f"- {reason}" for reason in decision.reasons)))
    message.set_content("\n".join(lines))
    return message


def send_email_notification(
    config: EmailNotificationConfig,
    invoice: Invoice,
    decision: ProcessingDecision,
    *,
    smtp_factory: Callable[..., smtplib.SMTP_SSL] = smtplib.SMTP_SSL,
) -> None:
    """Send one SSL-protected SMTP notification."""

    message = build_notification(invoice, decision)
    message["From"] = config.sender
    message["To"] = config.recipient
    try:
        with smtp_factory(
            config.host, config.port, context=ssl.create_default_context()
        ) as smtp:
            smtp.login(config.username, config.password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        raise NotificationError(f"Email notification failed: {error}") from error
