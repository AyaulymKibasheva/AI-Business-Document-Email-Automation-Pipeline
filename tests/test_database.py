"""Integration tests for database persistence."""

import unittest
from datetime import date, datetime, timezone

from sqlalchemy import create_engine, inspect

from app.database import (
    DuplicateDocumentError,
    calculate_file_hash,
    count_records,
    find_duplicate_document,
    initialize_database,
    save_processing_result,
)
from app.status import failed, processed
from app.validator import Invoice


class DatabasePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        initialize_database(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_creates_required_tables(self) -> None:
        self.assertEqual(
            set(inspect(self.engine).get_table_names()),
            {"documents", "errors", "extracted_data", "processing_runs"},
        )

    def test_saves_processed_invoice_and_run(self) -> None:
        invoice = Invoice(
            invoice_number="INV-1048",
            company_name="ABC Ltd",
            invoice_date=date(2026, 9, 15),
            due_date=date(2026, 10, 15),
            currency="USD",
            subtotal=1000.0,
            tax=250.0,
            total=1250.0,
            email="billing@example.com",
        )

        document_id = save_processing_result(
            self.engine,
            filename="invoice.pdf",
            file_hash="a" * 64,
            document_type="invoice",
            decision=processed(),
            started_at=datetime.now(timezone.utc),
            stage="complete",
            invoice=invoice,
            confidence=0.95,
            uncertain_fields=[],
            model_name="qwen2.5:3b",
        )

        self.assertEqual(document_id, 1)
        self.assertEqual(
            count_records(self.engine),
            {
                "documents": 1,
                "extracted_data": 1,
                "processing_runs": 1,
                "errors": 0,
            },
        )

    def test_saves_failed_run_and_error(self) -> None:
        save_processing_result(
            self.engine,
            filename="broken.pdf",
            file_hash="b" * 64,
            document_type=None,
            decision=failed("Could not read PDF"),
            started_at=datetime.now(timezone.utc),
            stage="text_extraction",
        )

        self.assertEqual(count_records(self.engine)["errors"], 1)

    def test_rejects_duplicate_file_hash(self) -> None:
        common = {
            "engine": self.engine,
            "file_hash": "c" * 64,
            "document_type": "other",
            "decision": processed(),
            "started_at": datetime.now(timezone.utc),
            "stage": "complete",
        }
        save_processing_result(filename="first.txt", **common)

        with self.assertRaises(DuplicateDocumentError):
            save_processing_result(filename="second.txt", **common)

        self.assertEqual(count_records(self.engine)["documents"], 1)

    def test_finds_duplicate_file_hash(self) -> None:
        save_processing_result(
            self.engine,
            filename="first.txt",
            file_hash="d" * 64,
            document_type="other",
            decision=processed(),
            started_at=datetime.now(timezone.utc),
            stage="complete",
        )

        self.assertEqual(
            find_duplicate_document(self.engine, file_hash="d" * 64), 1
        )

    def test_calculates_stable_sha256_hash(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invoice.txt"
            path.write_bytes(b"same invoice")
            first = calculate_file_hash(path)
            second = calculate_file_hash(path)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
