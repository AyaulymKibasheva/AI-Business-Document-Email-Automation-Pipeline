"""Tests for IMAP document attachment ingestion."""

import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

from app.email_reader import EmailConfig, EmailIngestionError, download_unread_attachments


class FakeImapClient:
    def __init__(self, host: str, port: int, raw_message: bytes) -> None:
        self.raw_message = raw_message
        self.calls: list[tuple] = []

    def login(self, username: str, password: str):
        self.calls.append(("login", username, password))
        return "OK", []

    def select(self, mailbox: str):
        self.calls.append(("select", mailbox))
        return "OK", [b"1"]

    def uid(self, command: str, *args):
        self.calls.append(("uid", command, *args))
        if command == "search":
            return "OK", [b"42"]
        if command == "fetch":
            return "OK", [(b"42 (RFC822)", self.raw_message)]
        return "OK", []

    def logout(self):
        self.calls.append(("logout",))


class EmailReaderTests(unittest.TestCase):
    def _message(self) -> bytes:
        message = EmailMessage()
        message["From"] = "supplier@example.com"
        message["To"] = "documents@example.com"
        message["Subject"] = "Invoice"
        message.set_content("Please see the attached invoice.")
        message.add_attachment(
            b"Invoice INV-42", maintype="text", subtype="plain", filename="invoice.txt"
        )
        message.add_attachment(
            b"not supported", maintype="image", subtype="png", filename="image.png"
        )
        return message.as_bytes()

    def test_downloads_supported_attachment_and_marks_message_seen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeImapClient("host", 993, self._message())
            config = EmailConfig(
                host="host",
                username="user",
                password="secret",
                attachment_dir=Path(directory),
            )

            files = download_unread_attachments(
                config, client_factory=lambda host, port: client
            )

            self.assertEqual([path.name for path in files], ["42_invoice.txt"])
            self.assertEqual(files[0].read_bytes(), b"Invoice INV-42")
            self.assertIn(("uid", "store", b"42", "+FLAGS", "(\\Seen)"), client.calls)

    def test_skips_oversized_attachment_without_marking_seen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeImapClient("host", 993, self._message())
            config = EmailConfig(
                host="host",
                username="user",
                password="secret",
                attachment_dir=Path(directory),
                max_attachment_bytes=2,
            )

            files = download_unread_attachments(
                config, client_factory=lambda host, port: client
            )

            self.assertEqual(files, [])
            self.assertFalse(any(call[0:2] == ("uid", "store") for call in client.calls))

    def test_requires_email_environment_settings(self) -> None:
        from unittest.mock import patch

        with patch.dict("os.environ", {}, clear=True), patch(
            "app.email_reader.load_dotenv"
        ):
            with self.assertRaises(EmailIngestionError):
                EmailConfig.from_env()


if __name__ == "__main__":
    unittest.main()
