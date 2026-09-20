"""Download supported document attachments from an IMAP inbox."""

from __future__ import annotations

import imaplib
import os
import re
from dataclasses import dataclass
from email import message_from_bytes
from email.message import Message
from email.policy import default
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from app.parser import SUPPORTED_EXTENSIONS

DEFAULT_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class EmailIngestionError(RuntimeError):
    """Raised when inbox configuration or retrieval fails."""


@dataclass(frozen=True)
class EmailConfig:
    """IMAP connection settings loaded from local environment variables."""

    host: str
    username: str
    password: str
    port: int = 993
    mailbox: str = "INBOX"
    attachment_dir: Path = Path("data/email_attachments")
    max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES
    max_messages: int = 25

    @classmethod
    def from_env(cls) -> "EmailConfig":
        load_dotenv()
        required = {
            "IMAP_HOST": os.getenv("IMAP_HOST"),
            "IMAP_USERNAME": os.getenv("IMAP_USERNAME"),
            "IMAP_PASSWORD": os.getenv("IMAP_PASSWORD"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise EmailIngestionError(
                "Missing email settings: " + ", ".join(missing)
            )
        try:
            port = int(os.getenv("IMAP_PORT", "993"))
            max_bytes = int(
                os.getenv("EMAIL_MAX_ATTACHMENT_BYTES", str(DEFAULT_MAX_ATTACHMENT_BYTES))
            )
            max_messages = int(os.getenv("EMAIL_MAX_MESSAGES", "25"))
        except ValueError as error:
            raise EmailIngestionError("Email port and size limit must be integers") from error

        return cls(
            host=required["IMAP_HOST"] or "",
            username=required["IMAP_USERNAME"] or "",
            password=required["IMAP_PASSWORD"] or "",
            port=port,
            mailbox=os.getenv("IMAP_MAILBOX", "INBOX"),
            attachment_dir=Path(
                os.getenv("EMAIL_ATTACHMENT_DIR", "data/email_attachments")
            ),
            max_attachment_bytes=max_bytes,
            max_messages=max_messages,
        )


def _safe_filename(filename: str) -> str:
    """Remove path components and unsafe characters from an attachment name."""

    basename = Path(filename.replace("\\", "/")).name
    cleaned = re.sub(r"[^\w.() -]", "_", basename, flags=re.UNICODE).strip(" .")
    return cleaned or "attachment"


def _supported_attachments(message: Message) -> list[tuple[str, bytes]]:
    attachments: list[tuple[str, bytes]] = []
    for part in message.walk():
        filename = part.get_filename()
        if not filename or Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        payload = part.get_payload(decode=True)
        if payload is not None:
            attachments.append((_safe_filename(filename), payload))
    return attachments


def download_unread_attachments(
    config: EmailConfig,
    *,
    client_factory: Callable[..., imaplib.IMAP4_SSL] = imaplib.IMAP4_SSL,
) -> list[Path]:
    """Download supported attachments and mark their messages as read."""

    config.attachment_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    client = None
    try:
        client = client_factory(config.host, config.port)
        client.login(config.username, config.password)
        status, _ = client.select(config.mailbox)
        if status != "OK":
            raise EmailIngestionError(f"Could not open mailbox: {config.mailbox}")
        status, data = client.uid("search", None, "UNSEEN")
        if status != "OK":
            raise EmailIngestionError("Could not search unread messages")

        message_ids = data[0].split() if data and data[0] else []
        # Newest UIDs are last. Limit each run so a large old inbox cannot
        # block automation indefinitely.
        message_ids = message_ids[-config.max_messages :]
        for message_id in message_ids:
            status, response = client.uid("fetch", message_id, "(RFC822)")
            if status != "OK" or not response:
                continue
            raw_message = next(
                (item[1] for item in response if isinstance(item, tuple)), None
            )
            if not raw_message:
                continue
            message = message_from_bytes(raw_message, policy=default)
            attachments = _supported_attachments(message)
            saved_for_message: list[Path] = []
            for filename, payload in attachments:
                if len(payload) > config.max_attachment_bytes:
                    continue
                uid = message_id.decode("ascii", errors="ignore")
                destination = config.attachment_dir / f"{uid}_{filename}"
                destination.write_bytes(payload)
                saved_for_message.append(destination.resolve())
            if saved_for_message:
                downloaded.extend(saved_for_message)
                client.uid("store", message_id, "+FLAGS", "(\\Seen)")
        return downloaded
    except EmailIngestionError:
        raise
    except (imaplib.IMAP4.error, OSError) as error:
        raise EmailIngestionError(f"Email ingestion failed: {error}") from error
    finally:
        if client is not None:
            try:
                client.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
