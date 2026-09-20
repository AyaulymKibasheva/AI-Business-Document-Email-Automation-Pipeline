"""Tests for stage 14 email notifications."""

import unittest
from datetime import date
from unittest.mock import patch

from app.notifier import (
    EmailNotificationConfig,
    build_notification,
    send_email_notification,
)
from app.status import ProcessingDecision, ProcessingStatus, processed
from app.validator import Invoice


class FakeSmtp:
    def __init__(self, host, port, context) -> None:
        self.host = host
        self.port = port
        self.login_values = None
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, username, password):
        self.login_values = (username, password)

    def send_message(self, message):
        self.message = message


class EmailNotifierTests(unittest.TestCase):
    def _invoice(self) -> Invoice:
        return Invoice(
            invoice_number="INV-14",
            company_name="Notify Ltd",
            invoice_date=date(2026, 9, 20),
            due_date=None,
            currency="USD",
            subtotal=80,
            tax=20,
            total=100,
            email="billing@notify.example",
        )

    def test_builds_processed_notification(self) -> None:
        message = build_notification(self._invoice(), processed())

        self.assertIn("processed successfully", message["Subject"])
        self.assertIn("100.00 USD", message.get_content())

    def test_builds_review_notification_with_reasons(self) -> None:
        decision = ProcessingDecision(
            ProcessingStatus.NEEDS_REVIEW, ("total validation failed",)
        )
        message = build_notification(self._invoice(), decision)

        self.assertIn("requires review", message["Subject"])
        self.assertIn("total validation failed", message.get_content())

    def test_sends_with_smtp_ssl(self) -> None:
        smtp = FakeSmtp("", 0, None)
        config = EmailNotificationConfig(
            host="smtp.gmail.com",
            port=465,
            username="sender@example.com",
            password="app-password",
            recipient="recipient@example.com",
            sender="sender@example.com",
        )

        send_email_notification(
            config,
            self._invoice(),
            processed(),
            smtp_factory=lambda host, port, context: smtp,
        )

        self.assertEqual(smtp.login_values, ("sender@example.com", "app-password"))
        self.assertEqual(smtp.message["To"], "recipient@example.com")

    def test_reuses_gmail_ingestion_credentials(self) -> None:
        with patch.dict(
            "os.environ",
            {"IMAP_USERNAME": "gmail@example.com", "IMAP_PASSWORD": "secret"},
            clear=True,
        ), patch("app.notifier.load_dotenv"):
            config = EmailNotificationConfig.from_env()

        self.assertEqual(config.username, "gmail@example.com")
        self.assertEqual(config.recipient, "gmail@example.com")


if __name__ == "__main__":
    unittest.main()
