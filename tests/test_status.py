"""Tests for document processing status decisions."""

import unittest

from app.data_extractor import InvoiceData
from app.status import ProcessingStatus, assess_invoice, failed, processed
from app.validator import BusinessValidationResult, ValidationIssue


def extraction(**overrides: object) -> InvoiceData:
    values = {
        "invoice_number": "INV-1048",
        "company_name": "ABC Ltd",
        "invoice_date": "2026-09-15",
        "due_date": "2026-10-15",
        "currency": "USD",
        "subtotal": 1000.0,
        "tax": 250.0,
        "total": 1250.0,
        "email": "billing@example.com",
        "confidence": 0.95,
        "uncertain_fields": [],
    }
    values.update(overrides)
    return InvoiceData.model_validate(values)


class ProcessingStatusTests(unittest.TestCase):
    def test_marks_valid_invoice_processed(self) -> None:
        decision = assess_invoice(
            extraction(), business_validation=BusinessValidationResult(issues=())
        )

        self.assertEqual(decision.status, ProcessingStatus.PROCESSED)
        self.assertEqual(decision.reasons, ())

    def test_marks_low_confidence_for_review(self) -> None:
        decision = assess_invoice(extraction(confidence=0.55))

        self.assertEqual(decision.status, ProcessingStatus.NEEDS_REVIEW)
        self.assertIn("below", decision.reasons[0])

    def test_marks_uncertain_fields_for_review(self) -> None:
        decision = assess_invoice(extraction(uncertain_fields=["total", "tax"]))

        self.assertEqual(decision.status, ProcessingStatus.NEEDS_REVIEW)
        self.assertIn("total, tax", decision.reasons[0])

    def test_marks_schema_error_for_review(self) -> None:
        decision = assess_invoice(extraction(), schema_error="invoice_number is missing")

        self.assertEqual(decision.status, ProcessingStatus.NEEDS_REVIEW)
        self.assertIn("invoice_number", decision.reasons[0])

    def test_marks_business_rule_failure_for_review(self) -> None:
        validation = BusinessValidationResult(
            issues=(ValidationIssue("total", "must be greater than zero"),)
        )

        decision = assess_invoice(extraction(), business_validation=validation)

        self.assertEqual(decision.status, ProcessingStatus.NEEDS_REVIEW)
        self.assertIn("total", decision.reasons[0])

    def test_explicit_processed_and_failed_decisions(self) -> None:
        self.assertEqual(processed().status, ProcessingStatus.PROCESSED)
        self.assertEqual(failed("Ollama unavailable").status, ProcessingStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
