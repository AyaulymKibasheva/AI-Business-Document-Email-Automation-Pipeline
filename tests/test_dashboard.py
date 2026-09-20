"""Data tests for the stage 19 dashboard."""

import unittest
from datetime import date, datetime, timezone

from sqlalchemy import create_engine

from app.database import dashboard_metrics, initialize_database, save_processing_result
from app.status import ProcessingDecision, ProcessingStatus, failed, processed
from app.validator import Invoice


class DashboardMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        initialize_database(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_returns_exact_dashboard_aggregates(self) -> None:
        invoice = Invoice(
            invoice_number="DASH-1",
            company_name="Blue Ltd",
            invoice_date=date(2026, 9, 21),
            due_date=None,
            currency="USD",
            subtotal=80,
            tax=20,
            total=100,
            email=None,
        )
        now = datetime.now(timezone.utc)
        save_processing_result(
            self.engine,
            filename="invoice.txt",
            file_hash="1" * 64,
            document_type="invoice",
            decision=processed(),
            started_at=now,
            stage="complete",
            invoice=invoice,
        )
        save_processing_result(
            self.engine,
            filename="review.txt",
            file_hash="2" * 64,
            document_type="invoice",
            decision=ProcessingDecision(
                ProcessingStatus.NEEDS_REVIEW, ("check total",)
            ),
            started_at=now,
            stage="business_validation",
        )
        save_processing_result(
            self.engine,
            filename="failed.txt",
            file_hash="3" * 64,
            document_type=None,
            decision=failed("broken"),
            started_at=now,
            stage="text_extraction",
        )

        metrics = dashboard_metrics(self.engine)

        self.assertEqual(metrics["total_documents"], 3)
        self.assertEqual(metrics["processed"], 1)
        self.assertEqual(metrics["needs_review"], 1)
        self.assertEqual(metrics["failed"], 1)
        self.assertEqual(metrics["total_invoice_amount"], 100.0)
        self.assertIsNotNone(metrics["last_processing_run"])


if __name__ == "__main__":
    unittest.main()
